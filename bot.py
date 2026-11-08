"""Forgepoint Command starter: safe read-only Discord and Google Sheets commands."""
import os
import logging
import base64
import json
import tempfile
import asyncio
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fps")
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1ZH5-ComS-Dv21bRGgM7GZ9SfS1bRcE6QfOXjTqshE6Y")

ROLES = ["FPS Command", "FPS Team Leader", "FPS Member", "FPS Anvil", "FPS Hammer",
         "FPS Raven", "FPS Titan", "FPS Aviation", "FPS Command Support", "FPS Medic"]
STRUCTURE = {
    "FPS INFORMATION": [("rules", True), ("announcements", True), ("chain-of-command", True),
                        ("company-roster", True), ("recruitment", False)],
    "FPS OPERATIONS": [("operations", False), ("contracts", True), ("standard-equipment", True),
                       ("equipment-shop", True), ("reputation", True)],
    "FPS TEAMS": [("anvil-team", False), ("hammer-team", False), ("raven-sta", False),
                  ("titan-heavy", False), ("aviation", False)],
    "FPS COMMAND": [("leadership", False), ("company-treasury", True)],
}
ROSTER = {
    "Command": ("Rex — Forge Actual; Kahuna — Forge Bravo", 2, 2),
    "Anvil": ("Bama — Anvil Actual", 1, 8),
    "Hammer": ("Freedlund — Hammer Actual; Stratt — A/ Team Leader; Lanal — Medic / GP", 3, 7),
    "Raven STA": ("Fridgy — Raven Actual", 1, 4),
    "Titan": ("Thorn — Titan Actual", 1, 4),
    "Command Support": ("Dark — Forge Fires", 1, 1),
    "Aviation": ("Kuba — Valkyrie Actual; Nolan — Crew Chief", 2, 4),
}
RULES = [
    ("Respect & conduct", "Treat teammates and other BMG members respectfully. Follow Discord and BMG rules. No harassment, discrimination, threats or deliberate disruption."),
    ("Chain of command", "Forge Actual (Rex) and Forge Bravo (Kahuna) lead FPS. Section leaders coordinate their sections. A/ Team Leaders stand in as needed, without inheriting a permanent radio callsign."),
    ("Operations", "Follow mission briefings, maintain disciplined comms, cooperate with teammates and uphold fair-play standards. Real-life obligations come first; communicate absences when possible."),
    ("Contracts & credits", "FPS credits are fictional campaign currency, not USD. Success pays 100% of agreed fees; legitimate failure pays 50% rounded UP; pending or void contracts pay zero. Shop purchases require Command approval."),
    ("Reputation", "OFFICIAL: FPS reputation starts at 50/100 and ranges from 0 to 100. Only completed, Forge Command-approved events in the Reputation Meter change the score. Higher reputation improves hiring access; it does not change standard contract CR payouts. Avoid double-penalizing the same incident."),
    ("Motto", "Forged into Soldiers."),
]

intents = discord.Intents.default()
# Full member listing is privileged; opt in only after enabling it in Discord Developer Portal.
intents.members = os.getenv("FPS_MEMBER_SYNC_ENABLED", "0").strip().lower() in ("1", "true", "yes")
bot = commands.Bot(command_prefix="!", intents=intents)


def sheet():
    import gspread
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_B64")
    if raw:
        info = json.loads(base64.b64decode(raw, validate=True).decode("utf-8"))
        client = gspread.service_account_from_dict(info)
    else:
        filename = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
        if not Path(filename).exists():
            raise RuntimeError("Google Sheets service account is not configured yet.")
        client = gspread.service_account(filename=filename)
    return client.open_by_key(SHEET_ID)


async def answer(interaction, message, private=True):
    if interaction.response.is_done():
        await interaction.followup.send(message[:1950], ephemeral=private)
    else:
        await interaction.response.send_message(message[:1950], ephemeral=private)


def is_admin(interaction):
    return interaction.guild is not None and interaction.user.guild_permissions.administrator


def is_command(interaction):
    if is_admin(interaction):
        return True
    return any(role.name == "FPS Command" for role in getattr(interaction.user, "roles", []))


@bot.event
async def on_ready():
    if not getattr(bot, "_fps_synced", False):
        if GUILD_ID:
            server = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=server)
            await bot.tree.sync(guild=server)
        else:
            await bot.tree.sync()
        bot._fps_synced = True
    log.info("Logged in as %s", bot.user)


@bot.tree.command(name="setup_fps", description="Preview or safely create Forgepoint's missing roles and channels")
@app_commands.describe(confirm="False previews; True creates missing server structure")
async def setup_fps(interaction: discord.Interaction, confirm: bool = False):
    if not is_admin(interaction):
        return await answer(interaction, "Only Discord server administrators can run FPS setup.")
    guild = interaction.guild
    if not guild:
        return await answer(interaction, "Run this command in the FPS Discord server.")
    missing_roles = [r for r in ROLES if discord.utils.get(guild.roles, name=r) is None]
    missing_cats = [c for c in STRUCTURE if discord.utils.get(guild.categories, name=c) is None]
    missing_channels = [name for entries in STRUCTURE.values() for name, _ in entries
                        if discord.utils.get(guild.text_channels, name=name) is None]
    if not confirm:
        return await answer(interaction,
            "**FPS PREVIEW — no changes made**\nRoles: " + (", ".join(missing_roles) or "none") +
            "\nCategories: " + (", ".join(missing_cats) or "none") +
            "\nChannels: " + (", ".join(missing_channels) or "none") +
            "\nRun `/setup_fps confirm:true` only after reviewing.")
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        for name in missing_roles:
            await guild.create_role(name=name, reason="FPS safe setup")
        for category_name, entries in STRUCTURE.items():
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name, reason="FPS safe setup")
            for name, info_only in entries:
                if discord.utils.get(guild.text_channels, name=name):
                    continue
                overwrites = {}
                if info_only:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(send_messages=False)
                    overwrites[guild.me] = discord.PermissionOverwrite(send_messages=True, view_channel=True)
                if category_name == "FPS COMMAND":
                    overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    command_role = discord.utils.get(guild.roles, name="FPS Command")
                    if command_role:
                        overwrites[command_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    overwrites[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                await guild.create_text_channel(name, category=category,
                                                overwrites=overwrites, reason="FPS safe setup")
        rules_channel = discord.utils.get(guild.text_channels, name="rules")
        if rules_channel and "rules" in missing_channels:
            for title, body in RULES:
                await rules_channel.send(embed=discord.Embed(title=title, description=body, color=0x5AA5A1))
        chain_channel = discord.utils.get(guild.text_channels, name="chain-of-command")
        if chain_channel and "chain-of-command" in missing_channels:
            await chain_channel.send("\n".join(f"**{team}** — {details[0]}" for team, details in ROSTER.items()))
        await answer(interaction, "FPS setup finished. Existing channels, roles, and permissions were left unchanged.")
    except discord.Forbidden:
        await answer(interaction, "Discord denied an action. Check Manage Channels/Roles and the bot role position.")
    except discord.HTTPException as exc:
        log.exception("FPS setup failed")
        await answer(interaction, f"Discord setup stopped: {str(exc)[:300]}")


@bot.tree.command(name="roster", description="Show FPS section roster")
@app_commands.describe(section="Leave blank for all FPS sections")
async def roster(interaction: discord.Interaction, section: str = ""):
    names = [
        name for name in ROSTER
        if not section or section.casefold() in name.casefold()
    ]
    if not names:
        return await answer(interaction, "No matching FPS section.")

    def load_live_roster():
        workbook = sheet()
        counts = workbook.worksheet("Personnel Dashboard").get("A11:D17")
        people = workbook.worksheet("Master Roster").get("A7:E46")
        figures = {}
        member_names = {name: [] for name in ROSTER}
        for row in counts:
            if len(row) >= 3 and row[0] in member_names:
                figures[row[0]] = (int(float(row[2])), int(float(row[1])))
        for row in people:
            if len(row) < 3 or row[0] not in member_names or not row[2]:
                continue
            display = row[2]
            callsign = row[3] if len(row) > 3 else ""
            billet = row[4] if len(row) > 4 else ""
            if callsign:
                display += " — " + callsign
            elif "Medic" in billet or "Crew Chief" in billet or "A/" in billet:
                display += " (" + billet + ")"
            member_names[row[0]].append(display)
        return figures, member_names

    try:
        figures, member_names = await asyncio.to_thread(load_live_roster)
        lines = []
        for name in names:
            assigned, capacity = figures.get(name, ROSTER[name][1:])
            details = "; ".join(member_names[name]) or "No members assigned"
            lines.append(f"**{name} — {assigned}/{capacity}**\n{details}")
    except Exception as exc:
        log.warning("Roster using snapshot: %s", exc)
        lines = [
            f"**{name} — {ROSTER[name][1]}/{ROSTER[name][2]}**\n{ROSTER[name][0]}"
            for name in names
        ]
    await answer(interaction, "\n\n".join(lines), private=False)


@bot.tree.command(name="treasury", description="Display live FPS treasury balance (Command only)")
async def treasury(interaction: discord.Interaction):
    if not is_command(interaction):
        return await answer(interaction, "FPS Command access required.")
    try:
        value = sheet().worksheet("FPS Treasury").acell("C11").value
        await answer(interaction, f"**FPS Treasury:** {value}", private=True)
    except Exception as exc:
        log.warning("Treasury sheet error: %s", exc)
        await answer(interaction, "Google Sheets is not configured or temporarily unavailable.")


@bot.tree.command(name="balance", description="Show the current FPS company credit balance to everyone in this server")
async def balance(interaction: discord.Interaction):
    """Public, read-only treasury balance. Does not expose the finance ledger."""
    if interaction.guild is None or (GUILD_ID and interaction.guild.id != GUILD_ID):
        return await answer(interaction, "This command is available only in the FPS Discord server.")

    # Unlike /treasury, this is available to every server member and is NOT ephemeral.
    # Fetch only the shareable C11 summary, not individual purchase or adjustment rows.
    await interaction.response.defer(thinking=True, ephemeral=False)
    try:
        balance_value = await asyncio.to_thread(
            lambda: sheet().worksheet("FPS Treasury").acell("C11").value
        )
        if not balance_value:
            raise ValueError("The treasury balance cell C11 is empty.")
        embed = discord.Embed(
            title="🏦 FORGEPOINT SECURITY | COMPANY BALANCE",
            description=f"**Current funds:** {balance_value}\n"
                        "Shared FPS campaign treasury • CR is fictional game currency.",
            color=0x137D73,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Live from FPS Master Sheet • run /balance to refresh")
        await interaction.followup.send(
            embed=embed,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except Exception:
        log.exception("Public treasury balance lookup failed")
        await interaction.followup.send(
            "I couldn't read the FPS treasury balance. No spreadsheet information was changed.",
            ephemeral=False,
        )


@bot.tree.command(name="shop", description="Browse FPS equipment prices")
@app_commands.describe(section="Optional partial section name")
async def shop(interaction: discord.Interaction, section: str = ""):
    try:
        rows = sheet().worksheet("Catalog").get("A7:G54")
        items = [r for r in rows if len(r) >= 5 and r[0].startswith("FPS-")
                 and (not section or section.lower() in r[1].lower())]
        if not items:
            return await answer(interaction, "No matching shop items.")
        lines = [f"`{r[0]}` {r[3]} — **{r[4]} CR** ({r[1]})" for r in items[:22]]
        await answer(interaction, "**FPS SHOP**\n" + "\n".join(lines), private=False)
    except Exception as exc:
        log.warning("Shop sheet error: %s", exc)
        await answer(interaction, "Google Sheets isn't available yet. Configure service account credentials first.")


@bot.tree.command(name="reputation", description="View official FPS reputation and its visual meter")
async def reputation(interaction: discord.Interaction):
    """Live, public, read-only company reputation status."""
    from fps_reputation_ui import score_number, reputation_bar

    try:
        rows = await asyncio.to_thread(
            lambda: sheet().worksheet("Reputation Meter").get("A6:G6")
        )
        if not rows:
            raise ValueError("Reputation Meter A6:G6 is empty")
        row = rows[0]
        score = score_number(row[2] if len(row) > 2 else "")
        tier = row[4] if len(row) > 4 and row[4] else "Unassigned"
        outlook = row[6] if len(row) > 6 else ""
        message = (
            "**📈 FPS REPUTATION — OFFICIAL**\n"
            + reputation_bar(score) + "\n"
            + "**{} / 100**  •  **{}**\n".format(score, tier)
            + "**Hiring outlook:** {}\n".format(outlook or "Not yet specified.")
            + "Approved mission events change reputation; the score affects "
              "hiring priority, **not** automatic contract payouts."
        )
        await answer(interaction, message, private=False)
    except Exception:
        log.exception("Official FPS reputation lookup failed")
        await answer(
            interaction,
            "Could not read the live FPS reputation score. "
            "No score or campaign record was changed.",
        )


@bot.tree.command(name="contracts", description="Show most recent FPS contract outcomes")
async def contracts(interaction: discord.Interaction):
    try:
        rows = sheet().worksheet("Contracts").get("A7:J106")
        results = [r for r in rows if len(r) >= 6 and r[5] in ("Success", "Failure")]
        display = results[-10:]
        if not display:
            return await answer(interaction, "No completed FPS contracts yet.", private=False)
        lines = [f"**{r[1] if len(r)>1 else 'Contract'}** — {r[5]}" for r in display]
        await answer(interaction, "**FPS Contracts**\n" + "\n".join(lines), private=False)
    except Exception as exc:
        log.warning("Contracts sheet error: %s", exc)
        await answer(interaction, "Google Sheets isn't available yet.")


# Manually sync the free Base Equipment tab to a single reusable channel post.
# This does not write to the spreadsheet or run background polling.
EQUIPMENT_POST_MARKER = "FPS_BASE_EQUIPMENT_V1 • /publish_equipment"
equipment_publish_lock = asyncio.Lock()


def load_base_equipment():
    """Read only the authoritative, bounded Base Equipment ranges."""
    worksheet = sheet().worksheet("Base Equipment")
    starter = worksheet.get("A6:E13")
    titan_rows = worksheet.get("A18:E18")
    policy_rows = worksheet.get("A22:A24")
    if len(starter) != 8 or any(len(item) < 5 for item in starter):
        raise ValueError("Standard loadout is incomplete; publication cancelled.")
    if not titan_rows or len(titan_rows[0]) < 5:
        raise ValueError("Titan first-issue equipment is missing; publication cancelled.")
    return starter, titan_rows[0], policy_rows


@bot.tree.command(name="publish_equipment", description="Post or refresh the free starter kit in #standard-equipment")
async def publish_equipment(interaction: discord.Interaction):
    """Command-only; update one bot-authored post instead of spamming duplicates."""
    if interaction.guild is None:
        return await answer(interaction, "Use this in your FPS Discord server.")
    if not is_command(interaction):
        return await answer(interaction, "Only FPS Command or server administrators can publish equipment.")
    channel = discord.utils.get(interaction.guild.text_channels, name="standard-equipment")
    if channel is None:
        return await answer(interaction, "I couldn't find #standard-equipment. Check the channel name or run server setup.")
    member = interaction.guild.me
    if member is None:
        return await answer(interaction, "Unable to verify my server permissions. Check the bot's server role.")
    permissions = channel.permissions_for(member)
    if not all((permissions.view_channel, permissions.send_messages,
                permissions.embed_links, permissions.read_message_history)):
        return await answer(interaction, "I need View Channel, Send Messages, Embed Links, and Read Message History in #standard-equipment.")

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        # gspread is synchronous: keep the Discord event loop responsive.
        starter, titan, policy_rows = await asyncio.to_thread(load_base_equipment)
    except Exception:
        log.exception("Unable to read the Base Equipment tab")
        return await answer(interaction, "Couldn't read the Base Equipment tab. No Discord post was changed.")

    embed = discord.Embed(
        title="⚒️ FORGEPOINT SECURITY | STANDARD EQUIPMENT",
        description="**Free starting equipment for every FPS operator.**\n"
                    "Pulled from the **Base Equipment** tab; run `/publish_equipment` again whenever that tab changes.",
        color=0x137D73,
        timestamp=discord.utils.utcnow(),
    )
    starter_lines = [f"• **{item[1]}** — {item[3]} CR _({item[0]})_" for item in starter]
    embed.add_field(name="STANDARD OPERATOR LOADOUT", value="\n".join(starter_lines), inline=False)
    embed.add_field(
        name="TITAN HEAVY — FIRST SECTION WEAPON",
        value=f"**{titan[1]}** — {titan[3]} CR\n{titan[2]}\n{titan[4]}",
        inline=False,
    )
    policies = [row[0] for row in policy_rows if row and row[0].strip()]
    if policies:
        embed.add_field(name="EQUIPMENT POLICY", value="\n".join(f"• {x}" for x in policies)[:1024], inline=False)
    embed.add_field(
        name="SOURCE OF TRUTH",
        value=f"[FPS Master Sheet — Base Equipment](https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=1604903172)",
        inline=False,
    )
    embed.set_footer(text=EQUIPMENT_POST_MARKER)

    try:
        async with equipment_publish_lock:
            previous = None
            async for message in channel.history(limit=250):
                if message.author.id == bot.user.id and any(
                    old.footer.text == EQUIPMENT_POST_MARKER for old in message.embeds
                ):
                    previous = message
                    break

            if previous:
                posted = await previous.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                result = "Updated the existing equipment post"
            else:
                posted = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                result = "Published the standard equipment post"

            if not posted.pinned and permissions.manage_messages:
                try:
                    await posted.pin(reason="FPS standard-equipment reference")
                except discord.HTTPException:
                    log.warning("Published equipment but could not pin the message")
            if not posted.pinned and not permissions.manage_messages:
                result += " (pin it manually if you want it pinned)"
        await answer(interaction, f"✅ {result} in {channel.mention}. No Google Sheets data was modified.")
    except discord.HTTPException:
        log.exception("Failed to publish FPS equipment")
        await answer(interaction, "Discord couldn't publish the equipment post. Check my channel permissions and try again.")



# Manual publications for essential FPS channels. Registration happens before sync.
from fps_publish import register_publishing

register_publishing(
    bot=bot,
    get_sheet=sheet,
    is_command=is_command,
    reply=answer,
    rules=RULES,
    sheet_id=SHEET_ID,
)

# FPS command staff can assign or remove EXISTING Discord roles.
# No role creation, no Sheets writes, and restricted to the FPS role allowlist.
from fps_roles import register_roles

register_roles(
    bot=bot,
    is_command=is_command,
    is_admin=is_admin,
    reply=answer,
    permitted_roles=ROLES,
    guild_id=GUILD_ID,
)

# FPS team role colors and opt-in public treasury channel setup.
from fps_appearance import register_appearance

register_appearance(
    bot=bot,
    get_sheet=sheet,
    is_command=is_command,
    is_admin=is_admin,
    reply=answer,
    guild_id=GUILD_ID,
)

# Optional admin-confirmed read-only permissions for non-exempt text channels.
from fps_channel_lock import register_readonly

register_readonly(
    bot=bot,
    is_admin=is_admin,
    reply=answer,
    guild_id=GUILD_ID,
)

# Private writable FPS team chats, scoped by the assigned team role.
from fps_team_chats import register_team_chats

register_team_chats(
    bot=bot,
    is_admin=is_admin,
    reply=answer,
    guild_id=GUILD_ID,
)


# Admin-confirmed import of Discord FPS Hammer role members into the existing
# Hammer Google Sheet roster. Requires privileged member intent opt-in.
from fps_hammer_sync import register_hammer_sync

register_hammer_sync(
    bot=bot,
    is_admin=is_admin,
    reply=answer,
    get_sheet=sheet,
    guild_id=GUILD_ID,
)


# Anvil leadership replacement, with admin preview/confirmation. Transfers
# only standard FPS Member / Anvil / Team Leader roles in live Discord.
from fps_lead_transfer import register_anvil_leader_transfer

register_anvil_leader_transfer(
    bot=bot,
    is_admin=is_admin,
    reply=answer,
    guild_id=GUILD_ID,
)

if __name__ == "__main__":
    if not TOKEN or TOKEN == "SET_PRIVATELY_IN_HOST":
        raise SystemExit("Set DISCORD_TOKEN as a private hosting environment variable first.")
    bot.run(TOKEN)
