"""Admin-confirmed, narrowly scoped Anvil leader handover in live Discord.

The Google Sheets leadership record is handled separately.
"""
import logging

import discord
from discord import app_commands

log = logging.getLogger("fps.anvil_handover")
REQUIRED = ("FPS Member", "FPS Anvil", "FPS Team Leader")
TARGET_USERNAME = "alabamianfox"


def register_anvil_leader_transfer(bot, is_admin, reply, guild_id=0):
    @bot.tree.command(
        name="replace_anvil_lead",
        description="Preview/transfer Wolf's Anvil roles to Bama (AlabamianFox)",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        wolf="Select Wolf's exact Discord account (outgoing leader)",
        bama="Select Bama's Discord account, username AlabamianFox",
        confirm="False previews; True assigns Bama and removes Wolf's FPS Anvil roles",
    )
    async def replace_anvil_lead(
        interaction: discord.Interaction,
        wolf: discord.Member,
        bama: discord.Member,
        confirm: bool = False,
    ):
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return await reply(interaction, "Use this in the FPS Discord server.")
        if not is_admin(interaction):
            return await reply(interaction, "Server administrator permission required.")
        if wolf.guild.id != guild.id or bama.guild.id != guild.id or wolf.id == bama.id:
            return await reply(interaction, "Select two different members of this server.")
        if bama.name.casefold() != TARGET_USERNAME:
            return await reply(
                interaction,
                "Selected Bama's Discord username is {}, not AlabamianFox. "
                "Select the correct account. No roles changed.".format(bama.name),
            )
        if not any(
            "wolf" in (name or "").casefold()
            for name in (wolf.name, wolf.display_name, wolf.nick, wolf.global_name)
        ):
            return await reply(
                interaction,
                "Outgoing member isn't named Wolf. Verify the source account "
                "before moving any roles. No changes made.",
            )
        if wolf.id == guild.owner_id or bama.id == guild.owner_id:
            return await reply(interaction, "Cannot transfer owner roles.")
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            return await reply(interaction, "Forgepoint Command needs Manage Roles.")
        if wolf.top_role >= bot_member.top_role or bama.top_role >= bot_member.top_role:
            return await reply(
                interaction, "The bot's top role must be above both selected users."
            )

        wolf_names = {role.name for role in wolf.roles}
        if not {"FPS Anvil", "FPS Team Leader"}.issubset(wolf_names):
            return await reply(
                interaction,
                "Selected Wolf account doesn't hold both FPS Anvil and "
                "FPS Team Leader. No changes made.",
            )

        found = []
        for name in REQUIRED:
            role = discord.utils.get(guild.roles, name=name)
            if role is None or role.is_default() or role.managed:
                return await reply(
                    interaction, "Missing/unmanageable FPS role: {}.".format(name)
                )
            if role >= bot_member.top_role:
                return await reply(
                    interaction, "Move bot role above {} first.".format(name)
                )
            elevated_flags = (
                "administrator", "manage_guild", "manage_roles", "manage_channels",
                "manage_webhooks", "ban_members", "kick_members", "moderate_members",
            )
            if any(getattr(role.permissions, flag, False) for flag in elevated_flags):
                return await reply(
                    interaction, "{} has privileged permissions. "
                    "Review manually; nothing changed.".format(name)
                )
            found.append(role)

        grant = [role for role in found if role not in bama.roles]
        revoke = [role for role in found if role in wolf.roles]
        untouched = [
            role.name for role in wolf.roles
            if not role.is_default() and role.name not in REQUIRED
        ]

        if not confirm:
            lines = [
                "**ANVIL LEADER REPLACEMENT — PREVIEW (no changes)**",
                "Outgoing: {} (username {}, ID {}).".format(
                    wolf.mention, wolf.name, wolf.id
                ),
                "Incoming: {} (username {}, ID {}).".format(
                    bama.mention, bama.name, bama.id
                ),
                "Bama: ANV-01 / Anvil Actual / Team Leader.",
                "Grant: {}.".format(", ".join(r.name for r in grant) or "already held"),
                "Revoke from Wolf: {}.".format(
                    ", ".join(r.name for r in revoke) or "none"
                ),
                "Wolf's other roles NOT copied or revoked: {}.".format(
                    ", ".join(untouched) or "none"
                ),
                "The Master Sheet is separate and already reflects Bama.",
                "Repeat with confirm:true to apply the Discord role handover.",
            ]
            return await reply(interaction, "\n".join(lines))

        await interaction.response.defer(thinking=True, ephemeral=True)
        if grant:
            try:
                await bama.add_roles(
                    *grant,
                    reason="Anvil Lead Bama appointed by {} ({})".format(
                        interaction.user, interaction.user.id
                    ),
                )
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Failed assigning Bama roles")
                return await reply(
                    interaction,
                    "Role assignment failed or partially succeeded. Wolf was not "
                    "intentionally stripped. Check Bama's roles before retrying.",
                )

        try:
            updated_wolf = await guild.fetch_member(wolf.id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return await reply(
                interaction,
                "Bama was granted roles, but Wolf couldn't be rechecked. "
                "Wolf may still have access; inspect his roles manually.",
            )

        remove_now = [role for role in found if role in updated_wolf.roles]
        if remove_now:
            try:
                await updated_wolf.remove_roles(
                    *remove_now,
                    reason="Inactive Wolf removed as Anvil Lead by {} ({})".format(
                        interaction.user, interaction.user.id
                    ),
                )
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Failed removing Wolf roles")
                return await reply(
                    interaction,
                    "Bama's roles were granted, but Wolf's role removal failed "
                    "or partly succeeded. Inspect Wolf's FPS access immediately.",
                )

        return await reply(
            interaction,
            "Bama (AlabamianFox) now holds the Anvil leadership roles. "
            "Wolf's scoped FPS Member/Anvil/Team Leader roles were revoked "
            "if held. Unrelated roles were left alone. Run /publish_roster "
            "and /publish_chain to update the public posts.",
        )
