"""Carefully scoped Discord role assignments for the existing FPS roles.

- Works with existing roles only (never creates or renames them).
- Only FPS Command and server administrators can use the commands.
- Granting or removing FPS Command itself requires a server administrator.
- No automatic side effects: membership in other teams and the Google Sheet
  are left unchanged.
"""
import logging

import discord
from discord import app_commands

log = logging.getLogger("fps.roles")
PRIVILEGED_PERMISSIONS = (
    "administrator",
    "manage_roles",
    "manage_guild",
    "manage_channels",
    "manage_webhooks",
    "kick_members",
    "ban_members",
    "moderate_members",
)


def register_roles(bot, is_command, is_admin, reply, permitted_roles, guild_id=0):
    allowed = frozenset(permitted_roles)

    def validate(interaction, member, role):
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return "These commands can only be used in the FPS Discord server."

        if not is_command(interaction):
            return "Only FPS Command or server administrators can manage FPS roles."

        if not isinstance(member, discord.Member) or member.guild.id != guild.id:
            return "Choose a current member of this FPS server."

        if role.guild.id != guild.id or role.name not in allowed:
            return "Choose an existing FPS role (Command, Team Leader, Member, or an FPS section)."

        if role.is_default() or role.managed:
            return "That role cannot be managed by Forgepoint Command."

        admin = is_admin(interaction)
        if role.name == "FPS Command" and not admin:
            return "Only Discord server administrators can assign or remove the FPS Command role."

        # A privileged pre-existing role may have gained Discord management
        # powers since the initial FPS setup. Only server admins may grant it.
        if not admin and any(getattr(role.permissions, name, False)
                             for name in PRIVILEGED_PERMISSIONS):
            return "That role has elevated Discord permissions. Ask a server administrator."

        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            return "The bot needs Manage Roles permission to do that."

        if role >= bot_member.top_role:
            return ("Move the Forgepoint Command bot's role ABOVE the FPS role "
                    "you want it to manage in Discord Server Settings → Roles.")

        # Discord role hierarchy also limits who can assign high roles.
        actor = interaction.user
        if guild.owner_id != actor.id:
            if role >= actor.top_role:
                return "Your own Discord role must be above the role you want to manage."
            if member.id != actor.id and member.top_role >= actor.top_role:
                return "You cannot manage the roles of a member at or above your role."

        return None

    @bot.tree.command(name="assign_role", description="Assign an existing FPS role to a server member")
    @app_commands.guild_only()
    @app_commands.describe(member="FPS member to give the role to",
                           role="Existing FPS role (pick one from Discord's list)")
    async def assign_role(interaction: discord.Interaction,
                          member: discord.Member, role: discord.Role):
        problem = validate(interaction, member, role)
        if problem:
            return await reply(interaction, problem)
        if role in member.roles:
            return await reply(interaction, "{} already has {}.".format(
                member.mention, role.mention))
        try:
            await member.add_roles(
                role, reason="FPS role assigned by {} (ID {})".format(
                    interaction.user, interaction.user.id))
        except discord.Forbidden:
            return await reply(interaction, "Discord refused the role change. Check Manage Roles and the bot's role position.")
        except discord.HTTPException:
            log.exception("Could not assign FPS role")
            return await reply(interaction, "Discord couldn't assign the role. Try again.")
        await reply(interaction, "✅ Assigned **{}** to **{}**. This changed Discord only; the Google Sheets roster was not edited.".format(
            role.name, member.display_name))

    @bot.tree.command(name="remove_role", description="Remove an existing FPS role from a server member")
    @app_commands.guild_only()
    @app_commands.describe(member="FPS member to remove the role from",
                           role="Existing FPS role (pick one from Discord's list)")
    async def remove_role(interaction: discord.Interaction,
                          member: discord.Member, role: discord.Role):
        problem = validate(interaction, member, role)
        if problem:
            return await reply(interaction, problem)
        if role not in member.roles:
            return await reply(interaction, "{} doesn't have {}.".format(
                member.mention, role.mention))
        try:
            await member.remove_roles(
                role, reason="FPS role removed by {} (ID {})".format(
                    interaction.user, interaction.user.id))
        except discord.Forbidden:
            return await reply(interaction, "Discord refused the role change. Check Manage Roles and the bot's role position.")
        except discord.HTTPException:
            log.exception("Could not remove FPS role")
            return await reply(interaction, "Discord couldn't remove the role. Try again.")
        await reply(interaction, "✅ Removed **{}** from **{}**. This changed Discord only; the Google Sheets roster was not edited.".format(
            role.name, member.display_name))
