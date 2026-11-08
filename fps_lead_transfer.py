"""Admin-confirmed handover of FPS Anvil roles to Bama (AlabamianFox).

Works even when Wolf has left the server or already lost Anvil roles. Does not
transfer privileged/unrelated roles, change any Google Sheets, or auto-run.
"""
import logging
import discord
from discord import app_commands

log = logging.getLogger("fps.anvil_handover")
TARGET_ALIASES = {"alabamianfox", "bama"}
REQUIRED_ROLE_NAMES = ("FPS Member", "FPS Anvil", "FPS Team Leader")
ELEVATED_PERMISSIONS = (
    "administrator", "manage_guild", "manage_roles", "manage_channels",
    "manage_webhooks", "kick_members", "ban_members", "moderate_members",
)


def register_anvil_leader_transfer(bot, is_admin, reply, guild_id=0):
    @bot.tree.command(
        name="replace_anvil_lead",
        description="Preview or make Bama Anvil lead; optionally remove Wolf's FPS roles",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        bama="Choose Bama's server account (Discord: AlabamianFox)",
        wolf="Optional: select Wolf if he is still in this server",
        confirm="False previews; True grants Bama roles and removes Wolf's scoped FPS roles",
    )
    async def replace_anvil_lead(
        interaction: discord.Interaction,
        bama: discord.Member,
        wolf: discord.Member | None = None,
        confirm: bool = False,
    ):
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return await reply(interaction, "Use this in the FPS Discord server.")
        if not is_admin(interaction):
            return await reply(
                interaction,
                "A Discord server administrator must approve leadership role transfers.",
            )
        if bama.guild.id != guild.id or (wolf is not None and wolf.guild.id != guild.id):
            return await reply(interaction, "Select current members of this server.")
        if wolf is not None and bama.id == wolf.id:
            return await reply(interaction, "Bama and Wolf must be different accounts.")
        if bama.id == guild.owner_id or (wolf is not None and wolf.id == guild.owner_id):
            return await reply(interaction, "Server-owner roles cannot be transferred.")
        labels = {str(label).strip().casefold()
                  for label in (
                      bama.name, bama.nick, bama.global_name, bama.display_name
                  ) if label}
        if not TARGET_ALIASES.intersection(labels):
            return await reply(
                interaction,
                "Chosen replacement is {} (username {}), not recognizably "
                "AlabamianFox/Bama. Select the correct account; no changes made."
                .format(bama.mention, bama.name),
            )

        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            return await reply(
                interaction,
                "Forgepoint Command needs the Discord **Manage Roles** permission.",
            )
        if bama.top_role >= me.top_role or (
            wolf is not None and wolf.top_role >= me.top_role
        ):
            return await reply(
                interaction,
                "Move Forgepoint Command's role **above both members' highest roles** "
                "in Discord Server Settings. No roles changed.",
            )

        roles = []
        for name in REQUIRED_ROLE_NAMES:
            role = discord.utils.get(guild.roles, name=name)
            if role is None or role.is_default() or role.managed:
                return await reply(
                    interaction, "Role {} is missing or cannot be managed.".format(name)
                )
            if role >= me.top_role:
                return await reply(
                    interaction,
                    "Bot role must be above {} in Server Settings → Roles.".format(name),
                )
            if any(getattr(role.permissions, flag, False)
                   for flag in ELEVATED_PERMISSIONS):
                return await reply(
                    interaction,
                    "{} has elevated permissions. Review manually; no changes made."
                    .format(name),
                )
            roles.append(role)

        # Wolf is OPTIONAL; he may have left, been kicked, or lost his roles.
        grant = [role for role in roles if role not in bama.roles]
        revoke = [role for role in roles if wolf is not None and role in wolf.roles]
        other_wolf_roles = [
            role.name for role in wolf.roles
            if not role.is_default() and role.name not in REQUIRED_ROLE_NAMES
        ] if wolf is not None else []

        if not confirm:
            preview = [
                "**ANVIL LEAD TRANSFER — PREVIEW ONLY**",
                "New lead: {} (username: {}; ID: {}).".format(
                    bama.mention, bama.name, bama.id
                ),
                "ANV-01 | Anvil Actual | Bama.",
                "Grant Bama: {}.".format(", ".join(x.name for x in grant) or "already held"),
                "Former leader: {}.".format(
                    "{} (username: {}; ID: {})".format(
                        wolf.mention, wolf.name, wolf.id
                    ) if wolf else "not selected / no longer in server"
                ),
                "Remove from Wolf: {}.".format(
                    ", ".join(x.name for x in revoke) or "nothing"
                ),
                "Other Wolf roles LEFT ALONE: {}.".format(
                    ", ".join(other_wolf_roles) or "none or Wolf not selected"
                ),
                "The Master Sheet already lists Bama. No sheet edit will occur.",
                "Run again with confirm:true to apply to Discord.",
            ]
            return await reply(interaction, "\n".join(preview))

        await interaction.response.defer(ephemeral=True, thinking=True)
        # Grant first so a removal failure cannot strand the team without its lead.
        if grant:
            try:
                await bama.add_roles(
                    *grant,
                    reason="Bama promoted to FPS Anvil Actual by {} ({})".format(
                        interaction.user, interaction.user.id
                    ),
                )
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Could not grant Anvil leader roles")
                return await reply(
                    interaction,
                    "Grant failed or partly succeeded. Check Bama's roles. "
                    "No Wolf roles were intentionally removed.",
                )

        if wolf is None:
            return await reply(
                interaction,
                "Bama's FPS Member, FPS Anvil, and FPS Team Leader roles are now "
                "assigned. Wolf was not selected, so his old roles were NOT "
                "modified. If Wolf is still in the server, remove the old Anvil "
                "leadership roles separately. Then run /publish_roster and "
                "/publish_chain.",
            )

        try:
            source = await guild.fetch_member(wolf.id)
        except discord.NotFound:
            return await reply(
                interaction,
                "Bama's leadership roles are assigned. Wolf has left the server, "
                "so there are no live member roles to revoke. Run /publish_roster "
                "and /publish_chain.",
            )
        except (discord.Forbidden, discord.HTTPException):
            return await reply(
                interaction,
                "Bama was assigned; Wolf's roles could not be checked. "
                "His access might remain. Check Wolf's roles manually.",
            )

        to_remove = [role for role in roles if role in source.roles]
        if to_remove:
            try:
                await source.remove_roles(
                    *to_remove,
                    reason="Wolf replaced as FPS Anvil Actual by {} ({})".format(
                        interaction.user, interaction.user.id
                    ),
                )
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Could not remove old Anvil roles")
                return await reply(
                    interaction,
                    "Bama's roles are assigned, but removing Wolf's roles failed "
                    "or only partly worked. Check Wolf's FPS access manually.",
                )

        return await reply(
            interaction,
            "Anvil role handover completed: Bama holds FPS Member, FPS Anvil "
            "and FPS Team Leader. Wolf's corresponding FPS roles were removed "
            "if held. Other roles were untouched. Publish with /publish_roster "
            "and /publish_chain.",
        )
