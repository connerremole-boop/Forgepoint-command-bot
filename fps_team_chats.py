"""Make each existing FPS team chat private and writable by that team.

Explicit administrator confirmation required; edits only the five named
team text channels, not category, voice, or other server permissions.
"""
import asyncio
import logging

import discord
from discord import app_commands

from fps_channel_lock import WRITE_FLAGS

log = logging.getLogger("fps.team_chats")

# The assigned team role and FPS Command are the only routine viewers/writers.
# Team Leaders must also carry their section role; generic FPS Team Leader
# alone does not unlock every section chat.
TEAMS = {
    "anvil-team": "FPS Anvil",
    "hammer-team": "FPS Hammer",
    "raven-sta": "FPS Raven",
    "titan-heavy": "FPS Titan",
    "aviation": "FPS Aviation",
}
COMMAND_ROLE = "FPS Command"


def copied(permission):
    return discord.PermissionOverwrite.from_pair(*permission.pair())


def desired_overwrites(channel, guild, team_role, command_role):
    """Preserve unrelated permission fields; replace only view/chat grants."""
    overrides = {target: copied(permission)
                 for target, permission in channel.overwrites.items()}

    base = overrides.get(guild.default_role, discord.PermissionOverwrite())
    base.view_channel = False
    base.read_message_history = False
    for flag in WRITE_FLAGS:
        setattr(base, flag, False)
    overrides[guild.default_role] = base

    authorized_ids = {guild.default_role.id, team_role.id, command_role.id}
    bot_member = guild.me
    if bot_member:
        authorized_ids.add(bot_member.id)

    # Existing explicit grants for unrelated roles or individual members
    # could bypass the @everyone deny. Clear positive grants for both view
    # and all chat permissions; preserve any explicit negative restrictions.
    clear_flags = ("view_channel", "read_message_history") + WRITE_FLAGS
    for target, original in list(overrides.items()):
        if target.id in authorized_ids:
            continue
        for flag in clear_flags:
            if getattr(original, flag) is True:
                setattr(original, flag, None)

    for target in (team_role, command_role):
        allowed = overrides.get(target, discord.PermissionOverwrite())
        allowed.view_channel = True
        allowed.read_message_history = True
        for flag in WRITE_FLAGS:
            setattr(allowed, flag, True)
        overrides[target] = allowed

    # Explicit bot access preserves future publisher and moderation commands
    # even if the bot has no FPS team membership.
    if bot_member:
        bot_access = overrides.get(bot_member, discord.PermissionOverwrite())
        bot_access.view_channel = True
        bot_access.read_message_history = True
        bot_access.send_messages = True
        bot_access.send_messages_in_threads = True
        bot_access.embed_links = True
        bot_access.use_application_commands = True
        overrides[bot_member] = bot_access

    return overrides


def register_team_chats(bot, is_admin, reply, guild_id=0):
    lock = asyncio.Lock()

    @bot.tree.command(
        name="setup_team_chats",
        description="Preview or make each FPS team text chat private and writable",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        confirm="False previews only; True applies private, writable team chat permissions",
    )
    async def setup_team_chats(interaction: discord.Interaction, confirm: bool = False):
        guild = interaction.guild
        if not guild or (guild_id and guild.id != guild_id):
            return await reply(interaction, "Run this in your FPS Discord server.")
        if not is_admin(interaction):
            return await reply(interaction, "Only Discord server administrators can update private team chat permissions.")

        command_role = discord.utils.get(guild.roles, name=COMMAND_ROLE)
        missing = []
        if command_role is None:
            missing.append(COMMAND_ROLE)
        targets = []
        for channel_name, team_role_name in TEAMS.items():
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            role = discord.utils.get(guild.roles, name=team_role_name)
            if channel is None:
                missing.append("#" + channel_name)
            if role is None:
                missing.append(team_role_name)
            if channel is not None and role is not None:
                targets.append((channel, role))
        if missing:
            return await reply(
                interaction,
                "Missing required FPS channels or roles: {}. No changes made.".format(
                    ", ".join(missing)
                ),
            )

        lines = [
            "• {} → {} + {}: **view and send messages**".format(
                channel.mention, role.mention, command_role.mention
            ) for channel, role in targets
        ]
        preview = (
            "**PRIVATE FPS TEAM CHATS — PREVIEW**\n"
            "Exactly five channels will become **private, writable chats**:\n"
            + "\n".join(lines) +
            "\n\nEvery other non-administrator role, including the generic "
            "FPS Team Leader role, will not gain access unless also assigned "
            "the matching team role. Existing direct visibility exceptions "
            "for unrelated members/roles will be removed.\n"
            "Discord server administrators can always access the channels. "
            "Forgepoint Command (the bot) retains message access.\n"
            "**Channel histories will only be visible to authorized members** "
            "after the change. Other channels and categories stay untouched.\n"
            "Run `/setup_team_chats confirm:true` to apply."
        )
        if not confirm:
            return await reply(interaction, preview)

        me = guild.me
        if me is None or not me.guild_permissions.manage_channels:
            return await reply(interaction, "Forgepoint Command needs Manage Channels permission.")

        blocked = [ch.name for ch, _ in targets
                   if not ch.permissions_for(me).manage_channels]
        if blocked:
            return await reply(
                interaction,
                "The bot cannot edit these channels: {}. No changes made.".format(
                    ", ".join(blocked)
                ),
            )

        try:
            intended = [
                (ch, role, desired_overwrites(ch, guild, role, command_role))
                for ch, role in targets
            ]
        except Exception:
            log.exception("Team channel preflight failed")
            return await reply(interaction, "Couldn't prepare team channel permissions. Nothing was changed.")

        # Discord limits the number of role/member overwrite entries per
        # channel. Fail before any edits if a channel would exceed the limit.
        over_limit = [ch.name for ch, _, overwrites in intended
                      if len(overwrites) > 100]
        if over_limit:
            return await reply(
                interaction,
                "These channels have too many individual permission overrides: "
                "{}. No changes made.".format(", ".join(over_limit)),
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        updated_channels, unchanged, failures = [], [], []
        async with lock:
            for channel, team_role, overrides in intended:
                if channel.overwrites == overrides:
                    unchanged.append(channel.name)
                    continue
                try:
                    edited = await channel.edit(
                        overwrites=overrides,
                        sync_permissions=False,
                        reason="FPS private writable team channel: {}".format(team_role.name),
                    )
                    current = edited or channel
                    visible = current.permissions_for(team_role)
                    command_visible = current.permissions_for(command_role)
                    # Discord owners/administrators inherently bypass normal
                    # channel restrictions; test role permissions, not people.
                    if not (visible.view_channel and visible.send_messages
                            and command_visible.view_channel
                            and command_visible.send_messages
                            and not current.permissions_for(guild.default_role).view_channel):
                        failures.append(channel.name + " (verify overrides)")
                    else:
                        updated_channels.append(channel.name)
                except discord.HTTPException:
                    log.exception("Failed to lock down %s", channel.name)
                    failures.append(channel.name)

        if failures:
            return await reply(
                interaction,
                "⚠️ Team chat setup partially completed. Updated: {}. "
                "Already correct: {}. Needs review: {}. "
                "Re-run the confirmed setup after fixing permissions.".format(
                    len(updated_channels), len(unchanged), ", ".join(failures)
                ),
            )
        return await reply(
            interaction,
            "✅ All five FPS team chats are now private and writable for "
            "their own team roles plus FPS Command (and server admins). "
            "{} updated; {} already correct. No other channels or Google Sheets were changed.".format(
                len(updated_channels), len(unchanged)
            ),
        )
