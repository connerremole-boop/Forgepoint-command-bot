"""FPS visual setup: color existing team roles and make only the treasury public.

Admins explicitly preview then confirm the permissions change. The treasury
is moved into FPS INFORMATION to preserve the privacy of FPS COMMAND.
"""
import asyncio
import logging

import discord
from discord import app_commands

log = logging.getLogger("fps.appearance")

# Bright and distinct on Discord's usual dark theme; no duplicate team colors.
TEAM_COLORS = {
    "FPS Anvil": 0x3B82F6,           # blue
    "FPS Hammer": 0xF97316,          # orange
    "FPS Raven": 0xA855F7,           # purple
    "FPS Titan": 0xEF4444,           # red
    "FPS Aviation": 0x06B6D4,        # cyan
    "FPS Command Support": 0x22C55E, # green
}
TREASURY_MARKER = "FPS_PUBLIC_TREASURY_REFERENCE_V1"
TREASURY_NAME = "company-treasury"
PUBLIC_CATEGORY = "FPS INFORMATION"


def register_appearance(bot, get_sheet, is_command, is_admin, reply, guild_id=0):
    publish_lock = asyncio.Lock()

    def target_guild(interaction):
        guild = interaction.guild
        return guild if guild is not None and (not guild_id or guild.id == guild_id) else None

    def treasury_channel(guild):
        return discord.utils.get(guild.text_channels, name=TREASURY_NAME)

    def is_public(channel, guild):
        # This is the effective view for @everyone. A special deny on a
        # different server-specific role may still restrict that member.
        return bool(channel.permissions_for(guild.default_role).view_channel)

    async def refresh_treasury(interaction, channel, publish_intro=False):
        """Use a single bot-authored public post; never touch transaction rows."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            balance = await asyncio.to_thread(
                lambda: get_sheet().worksheet("FPS Treasury").acell("C11").value
            )
            if not balance:
                raise ValueError("The live balance is empty")
        except Exception:
            log.exception("Unable to fetch treasury balance")
            return await reply(interaction, "Could not read FPS Treasury!C11. The Discord post was not updated.")

        embed = discord.Embed(
            title="🏦 FORGEPOINT SECURITY | COMPANY TREASURY",
            description="### 💰 CURRENT COMPANY BALANCE\n**{}**\n\n"
                        "All amounts are fictional FPS campaign credits (CR)."
                        "\n\nThis is a **manually refreshed snapshot**. "
                        "Any server member can use `/balance` for the latest balance.".format(balance),
            color=0xD4AF37,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Source: FPS Treasury!C11 • " + TREASURY_MARKER)

        try:
            async with publish_lock:
                existing = None
                async for msg in channel.history(limit=250):
                    if msg.author.id == bot.user.id and any(
                        (e.footer.text or "").endswith(TREASURY_MARKER) for e in msg.embeds
                    ):
                        existing = msg
                        break
                if existing:
                    posted = await existing.edit(
                        embed=embed, allowed_mentions=discord.AllowedMentions.none()
                    )
                    result = "Updated"
                else:
                    posted = await channel.send(
                        embed=embed, allowed_mentions=discord.AllowedMentions.none()
                    )
                    result = "Published"
                pin_note = ""
                permissions = channel.permissions_for(channel.guild.me)
                if not posted.pinned and permissions.manage_messages:
                    try:
                        await posted.pin(reason="FPS public treasury balance reference")
                    except discord.HTTPException:
                        pin_note = " (could not pin automatically)"
                elif not posted.pinned:
                    pin_note = " (pin it manually if you want)"
            extra = " Team colors and channel access were also configured." if publish_intro else ""
            return await reply(interaction, "✅ {} treasury balance in {}.{}{}".format(
                result, channel.mention, extra, pin_note))
        except discord.Forbidden:
            log.exception("Bot lacks public treasury message permissions")
            return await reply(interaction, "The channel is public, but the bot lacks permissions to publish there.")
        except discord.HTTPException:
            log.exception("Public treasury publish failed")
            return await reply(interaction, "Discord couldn't publish the treasury balance.")

    @bot.tree.command(
        name="setup_appearance",
        description="Preview or apply six unique FPS team colors and public treasury access",
    )
    @app_commands.guild_only()
    @app_commands.describe(confirm="False previews changes; True updates FPS role colors and opens treasury")
    async def setup_appearance(interaction: discord.Interaction, confirm: bool = False):
        guild = target_guild(interaction)
        if guild is None:
            return await reply(interaction, "Run this in the FPS Discord server.")
        if not is_admin(interaction):
            return await reply(interaction, "Only a Discord server administrator can change FPS role colors and channel visibility.")

        missing = [name for name in TEAM_COLORS
                   if discord.utils.get(guild.roles, name=name) is None]
        channel = treasury_channel(guild)
        public_category = discord.utils.get(guild.categories, name=PUBLIC_CATEGORY)
        if missing or not channel or not public_category:
            parts = []
            if missing:
                parts.append("Missing roles: " + ", ".join(missing))
            if not channel:
                parts.append("Missing #company-treasury")
            if not public_category:
                parts.append("Missing category FPS INFORMATION")
            return await reply(interaction, "\n".join(parts) + "\nRun /setup_fps first if the missing roles/channels need creation.")

        legend = "\n".join("• **{}** — `#{:06X}`".format(name, color)
                            for name, color in TEAM_COLORS.items())
        location = channel.category.name if channel.category else "(none)"
        preview = (
            "**FPS APPEARANCE PREVIEW**\n" + legend +
            "\n\n**Treasury:** Move #company-treasury from **{}** into **{}** and "
            "make it visible to @everyone (read-only for members).\n"
            "The existing FPS COMMAND category and leadership channels stay private.\n"
            "**Privacy notice:** Opening the existing treasury channel also makes "
            "its previously posted message history visible to members with access.\n"
            "The bot will post the current balance from FPS Treasury!C11.\n"
            "Run `/setup_appearance confirm:true` to apply.".format(location, PUBLIC_CATEGORY)
        )
        if not confirm:
            return await reply(interaction, preview)

        me = guild.me
        if me is None:
            return await reply(interaction, "I couldn't verify my Discord server permissions.")
        if not me.guild_permissions.manage_roles:
            return await reply(interaction, "I need **Manage Roles** permission.")
        if not channel.permissions_for(me).manage_channels:
            return await reply(interaction, "I need **Manage Channels** permission for #company-treasury.")
        if not all((channel.permissions_for(me).send_messages,
                    channel.permissions_for(me).embed_links,
                    channel.permissions_for(me).read_message_history)):
            return await reply(interaction, "I need Send Messages, Embed Links and Read Message History in #company-treasury.")

        roles = [(discord.utils.get(guild.roles, name=name), color)
                 for name, color in TEAM_COLORS.items()]
        inaccessible = [role.name for role, _ in roles
                        if role is None or role.managed or role >= me.top_role]
        if inaccessible:
            return await reply(interaction, "Put my bot role **above** these FPS roles before running setup: " +
                               ", ".join(inaccessible) + ". Nothing was changed.")

        modified = []
        try:
            for role, color in roles:
                if role.colour.value != color:
                    await role.edit(colour=discord.Colour(color), reason="FPS unique team identification colors")
                    modified.append(role.name)
        except discord.HTTPException:
            log.exception("Could not set all FPS team colors")
            return await reply(interaction, "Some team colors were updated, but Discord rejected another. "
                               "Check my Manage Roles permission and role hierarchy; re-run to finish.")

        # One atomic channel edit: preserve every other existing overwrite;
        # move only the treasury into the public informational category.
        overwrites = dict(channel.overwrites)
        default = channel.overwrites_for(guild.default_role)
        default.view_channel = True
        default.read_message_history = True
        default.send_messages = False
        default.send_messages_in_threads = False
        overwrites[guild.default_role] = default
        try:
            channel = await channel.edit(
                category=public_category,
                overwrites=overwrites,
                sync_permissions=False,
                reason="FPS public, read-only treasury; command channels remain private",
            )
        except discord.HTTPException:
            log.exception("Could not make FPS treasury public")
            return await reply(interaction, "Team role colors were updated, but Discord couldn't open "
                               "#company-treasury. Check my Manage Channels permission and retry.")

        if not is_public(channel, guild):
            return await reply(interaction, "Colors updated and treasury permissions changed, but "
                               "public visibility could not be verified. Please check the channel overrides.")

        await refresh_treasury(interaction, channel, publish_intro=True)

    @bot.tree.command(
        name="publish_treasury",
        description="Refresh the public, read-only FPS company treasury snapshot",
    )
    @app_commands.guild_only()
    async def publish_treasury(interaction: discord.Interaction):
        guild = target_guild(interaction)
        if guild is None:
            return await reply(interaction, "Run this in the FPS Discord server.")
        if not is_command(interaction):
            return await reply(interaction, "Only FPS Command or Discord administrators can publish the treasury.")
        channel = treasury_channel(guild)
        if channel is None:
            return await reply(interaction, "Missing #company-treasury.")
        if not is_public(channel, guild):
            return await reply(interaction, "The treasury channel is still private. "
                               "Ask a server administrator to run `/setup_appearance confirm:true`.")
        me = guild.me
        if me is None:
            return await reply(interaction, "I couldn't verify my Discord channel access.")
        perms = channel.permissions_for(me)
        if not all((perms.view_channel, perms.send_messages, perms.embed_links,
                    perms.read_message_history)):
            return await reply(interaction, "I need View Channel, Send Messages, Embed Links, and Read Message History.")
        await refresh_treasury(interaction, channel)
