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

        # Command staff may delegate normal FPS role assignments via the bot
        # even without personally holding Discord's Manage Roles permission.
        # Bot hierarchy plus the strict FPS allowlist are the boundaries.

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


    @bot.tree.command(
        name="assign_kuba",
        description="Assign Kuba's FPS Aviation Lead roles in one action",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member="Select Kuba's exact Discord account",
        confirm="False previews, True assigns all missing Aviation Lead roles",
    )
    async def assign_kuba(
        interaction: discord.Interaction,
        member: discord.Member,
        confirm: bool = False,
    ):
        """Give an explicitly selected member just the Aviation Lead roles."""
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return await reply(interaction, "This command can only be used in the FPS Discord server.")
        if not is_command(interaction):
            return await reply(
                interaction,
                "Only FPS Command or a Discord server administrator can assign Aviation Lead roles.",
            )
        if member.guild.id != guild.id:
            return await reply(interaction, "Choose Kuba from this Discord server's member list.")

        required_names = ("FPS Member", "FPS Aviation", "FPS Team Leader")
        required_roles = [discord.utils.get(guild.roles, name=name)
                          for name in required_names]
        missing_names = [name for name, role in zip(required_names, required_roles)
                         if role is None]
        if missing_names:
            return await reply(
                interaction,
                "These FPS roles don't exist yet: {}. Nothing changed.".format(
                    ", ".join(missing_names)
                ),
            )

        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            return await reply(
                interaction,
                "The bot needs Manage Roles permission to assign Aviation Lead roles.",
            )
        if member.id == guild.owner_id or member.top_role >= bot_member.top_role:
            return await reply(
                interaction,
                "The bot's highest role must be above Kuba's highest role, "
                "and the server owner cannot be managed by the bot.",
            )
        for role in required_roles:
            if role.is_default() or role.managed or role >= bot_member.top_role:
                return await reply(
                    interaction,
                    "The bot's role must be above **{}** in Discord Server Settings → Roles. "
                    "No changes made.".format(role.name),
                )
            if (not is_admin(interaction) and
                    any(getattr(role.permissions, flag, False)
                        for flag in PRIVILEGED_PERMISSIONS)):
                return await reply(
                    interaction,
                    "**{}** has elevated Discord permissions, so only a server administrator "
                    "may assign it. No changes made.".format(role.name),
                )

        to_add = [role for role in required_roles if role not in member.roles]
        if not to_add:
            return await reply(
                interaction,
                "✅ **{}** already has all three Aviation Lead roles: "
                "**FPS Member**, **FPS Aviation**, and **FPS Team Leader**. "
                "No changes needed.".format(member.display_name),
            )

        roles_list = ", ".join("**{}**".format(role.name) for role in required_roles)
        pending_list = ", ".join("**{}**".format(role.name) for role in to_add)
        if not confirm:
            return await reply(
                interaction,
                "**KUBA / AVIATION LEAD ROLE PREVIEW**\n"
                "Selected Discord member: {} (ID: `{}`)\n"
                "Required roles: {}\n"
                "Still to assign: {}\n"
                "**No FPS Command role will be granted.** "
                "Existing roles will not be removed. "
                "Google Sheets will not be modified.\n"
                "To apply, run `/assign_kuba` with the same member and `confirm:true`."
                .format(member.mention, member.id, roles_list, pending_list),
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        applied = []
        failure = None
        for role in to_add:
            try:
                await member.add_roles(
                    role,
                    reason="FPS Aviation Lead assignment by {} (ID {})".format(
                        interaction.user, interaction.user.id
                    ),
                )
                applied.append(role.name)
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Aviation Lead role assignment failed: %s", role.name)
                failure = role.name
                break

        if failure:
            return await reply(
                interaction,
                "⚠️ Partially assigned roles to {}. Added: {}. "
                "Couldn't assign **{}**. Check the bot's role hierarchy "
                "and run the command again after fixing permissions.".format(
                    member.mention, ", ".join(applied) or "none", failure
                ),
            )

        await reply(
            interaction,
            "✅ {} is now set up as **Aviation Lead**. Newly assigned: {}. "
            "Required roles: {}. His private **#aviation** chat access comes "
            "from FPS Aviation. No additional roles were removed, and the "
            "Google Sheets roster was not modified.".format(
                member.mention, ", ".join(applied), roles_list
            ),
        )
