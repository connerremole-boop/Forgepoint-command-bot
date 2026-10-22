"""Apply a deliberate FPS channel read-only policy without changing visibility.

This only edits text/forum channel *write* permission overrides. It does not
change @everyone visibility, existing categories, voice channels, or the two
excluded social/adults-only category trees. The action requires a preview and
explicit admin confirmation; it is never applied automatically on startup.
"""
import logging
import unicodedata

import discord
from discord import app_commands

log = logging.getLogger("fps.channel_permissions")

# Named exclusions are case-insensitive and ignore decorative punctuation.
EXCLUDED_CATEGORY_PREFIXES = ("textchannel", "adultsonly")

# Other than the named section-specific channels, only Command and Team
# Leaders may type outside the exempt social and adults-only categories.
GENERAL_WRITERS = ("FPS Command", "FPS Team Leader")
TEAM_CHANNEL_ROLES = {
    "anvil-team": ("FPS Anvil",),
    "hammer-team": ("FPS Hammer",),
    "raven-sta": ("FPS Raven",),
    "titan-heavy": ("FPS Titan",),
    "aviation": ("FPS Aviation", "FPS Command Support"),
}
SPECIAL_CHANNEL_ROLES = {
    "company-treasury": ("FPS Command",),
    "leadership": ("FPS Command",),
    # Forge Fires can post air-ground coordination in Operations.
    "operations": ("FPS Command", "FPS Team Leader", "FPS Command Support"),
}

# Blocking SEND_MESSAGES alone is not sufficient for threads or forum posts.
# Existing channel role/member exceptions must also be normalized.
WRITE_FLAGS = (
    "send_messages",
    "send_messages_in_threads",
    "create_public_threads",
    "create_private_threads",
    "send_voice_messages",
    "send_polls",
    "add_reactions",
    "use_application_commands",
)


def normalized(name):
    return "".join(
        char for char in unicodedata.normalize("NFKC", name).casefold()
        if char.isalnum()
    )


def is_excluded(channel):
    category = getattr(channel, "category", None)
    if category is None:
        return False
    category_name = normalized(category.name)
    return any(category_name.startswith(prefix) for prefix in EXCLUDED_CATEGORY_PREFIXES)


def proper_writers(channel):
    if channel.name in SPECIAL_CHANNEL_ROLES:
        return SPECIAL_CHANNEL_ROLES[channel.name]
    if channel.name in TEAM_CHANNEL_ROLES:
        return tuple(dict.fromkeys(
            GENERAL_WRITERS + TEAM_CHANNEL_ROLES[channel.name]
        ))
    if channel.category and normalized(channel.category.name) == "fpscommand":
        return ("FPS Command",)
    return GENERAL_WRITERS


def with_policy(channel, guild, writers):
    """Produce new channel overwrites, preserving all visibility rules."""
    overwrites = dict(channel.overwrites)
    everybody = guild.default_role

    base = channel.overwrites_for(everybody)
    for flag in WRITE_FLAGS:
        setattr(base, flag, False)
    overwrites[everybody] = base

    # Existing role and individual explicit write ALLOW overrides otherwise
    # bypass @everyone deny. Clear only their positive write permissions;
    # negative exceptions and every view/management permission remain intact.
    for target, old in list(overwrites.items()):
        if target.id == everybody.id:
            continue
        if isinstance(target, discord.Role) and target.name in writers:
            continue
        if isinstance(target, discord.Member) and guild.me and target.id == guild.me.id:
            continue
        changed = False
        updated = old
        for flag in WRITE_FLAGS:
            if getattr(updated, flag) is True:
                if not changed:
                    updated = discord.PermissionOverwrite.from_pair(*old.pair())
                    changed = True
                setattr(updated, flag, None)
        if changed:
            overwrites[target] = updated

    # Grant writing back to the appropriate FPS roles, without exposing any
    # channels already hidden from those roles.
    for role_name in writers:
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            raise ValueError("Missing Discord role: " + role_name)
        override = overwrites.get(role, discord.PermissionOverwrite())
        for flag in WRITE_FLAGS:
            setattr(override, flag, True)
        overwrites[role] = override

    # Keep the command bot able to publish and update its managed posts.
    if guild.me is not None:
        bot_override = overwrites.get(guild.me, discord.PermissionOverwrite())
        bot_override.send_messages = True
        bot_override.send_messages_in_threads = True
        bot_override.add_reactions = True
        overwrites[guild.me] = bot_override

    return overwrites


def register_readonly(bot, is_admin, reply, guild_id=0):
    @bot.tree.command(
        name="setup_readonly",
        description="Preview or apply FPS read-only channel permissions with role exceptions",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        confirm="False previews affected channels; True enforces the read-only policy",
    )
    async def setup_readonly(interaction: discord.Interaction, confirm: bool = False):
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return await reply(interaction, "Run this command in the FPS Discord server.")
        if not is_admin(interaction):
            return await reply(
                interaction, "Only a Discord server administrator can change FPS channel permissions."
            )

        # Text and forum channels only. Exclude voice/stage/category channels
        # and all text channels in the social and adults-only category trees.
        readable_types = (discord.TextChannel, discord.ForumChannel)
        targets = sorted(
            (ch for ch in guild.channels
             if isinstance(ch, readable_types) and not is_excluded(ch)),
            key=lambda ch: (ch.category.position if ch.category else -1,
                            ch.position, ch.name),
        )
        skipped = [
            ch for ch in guild.channels
            if isinstance(ch, readable_types) and is_excluded(ch)
        ]

        if not targets:
            return await reply(interaction, "No eligible text or forum channels found. No changes made.")

        missing = sorted({
            role for ch in targets for role in proper_writers(ch)
            if discord.utils.get(guild.roles, name=role) is None
        })
        if missing:
            return await reply(
                interaction,
                "Missing FPS roles: **{}**. Create the missing roles first. "
                "No channel permissions were changed.".format(", ".join(missing)),
            )

        # Offer a compact but accurate audit of the scope before making edits.
        preview_lines = []
        for ch in targets:
            location = ch.category.name if ch.category else "Uncategorized"
            roles = ", ".join(r.replace("FPS ", "") for r in proper_writers(ch))
            preview_lines.append("• #{} [{}] → {}".format(ch.name, location, roles))
        heading = (
            "**FPS READ-ONLY PERMISSIONS PREVIEW**\n"
            "**{} channels affected**; **{} channels skipped** inside "
            "Text Channel(s) / Adults Only. **Voice/stage channels are never touched.**\n"
            "All targeted channels stay visible/hidden as they are now; "
            "only write permissions are changed. Existing member-specific "
            "message allowances are removed so the proper roles control posting.\n"
            "Allowed writers: Command and Team Leaders generally; "
            "assigned team roles in their own channels; Command only in leadership/treasury.\n"
            "**Important:** Discord Administrators still bypass normal channel restrictions.\n\n"
        ).format(len(targets), len(skipped))
        details = "\n".join(preview_lines)
        if len(heading) + len(details) > 1650:
            space = max(150, 1650 - len(heading) - 80)
            details = details[:space].rsplit("\n", 1)[0]
            details += "\n• … more affected channels not shown in preview."
        if not confirm:
            return await reply(
                interaction,
                heading + details +
                "\n\nUse `/setup_readonly confirm:true` to apply.",
            )

        me = guild.me
        if me is None:
            return await reply(interaction, "I couldn't verify Forgepoint Command's server permissions.")
        if not (me.guild_permissions.manage_channels and me.guild_permissions.manage_roles):
            return await reply(interaction, "The bot needs **Manage Channels** and **Manage Roles** permissions.")

        blocked = [
            ch.name for ch in targets
            if not (ch.permissions_for(me).manage_channels and
                    ch.permissions_for(me).manage_roles)
        ]
        if blocked:
            return await reply(
                interaction,
                "The bot cannot edit these channels: **{}**. No changes were made. "
                "Check its Manage Channels/Manage Roles permissions.".format(
                    ", ".join(blocked[:15])
                ),
            )

        # Prebuild everything before making the first change. Neither the
        # channel's category nor its view_channel / member access is edited.
        try:
            changes = [(ch, with_policy(ch, guild, proper_writers(ch))) for ch in targets]
        except ValueError as error:
            return await reply(interaction, str(error) + ". No changes made.")

        await interaction.response.defer(ephemeral=True, thinking=True)
        succeeded, failed = [], []
        for channel, overwrites in changes:
            if dict(channel.overwrites) == overwrites:
                continue
            try:
                await channel.edit(
                    overwrites=overwrites,
                    sync_permissions=False,
                    reason="FPS role-based read-only text channel policy",
                )
                succeeded.append(channel.name)
            except discord.HTTPException:
                log.exception("Could not configure read-only channel %s", channel.name)
                failed.append(channel.name)

        if failed:
            return await reply(
                interaction,
                "⚠️ Updated **{}** channels but couldn't update **{}**. "
                "Failed: {}. Re-run `/setup_readonly confirm:true` to retry; "
                "it won't needlessly alter already-correct channels.".format(
                    len(succeeded), len(failed), ", ".join(failed[:12])
                ),
            )
        await reply(
            interaction,
            "✅ Read-only policy applied to **{}** eligible channels "
            "({} changed, {} already correct). **{}** exempt social/adults-only "
            "text channels and all voice/stage channels were untouched. "
            "Existing channel visibility and categories were preserved.".format(
                len(targets), len(succeeded), len(targets) - len(succeeded), len(skipped)
            ),
        )
