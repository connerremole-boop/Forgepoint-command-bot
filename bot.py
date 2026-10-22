"""Forgepoint Command starter: safe read-only Discord and Google Sheets commands."""
import os
import logging
import base64
import json
import tempfile
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
         "FPS Raven", "FPS Titan", "FPS Aviation", "FPS Command Support"]
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
    "Anvil": ("Wolf — Anvil Actual", 1, 8),
    "Hammer": ("Freedlund — Hammer Actual; Stratt — A/ Team Leader", 2, 7),
    "Raven STA": ("Fridgy — Raven Actual", 1, 4),
    "Titan": ("Thorn — Titan Actual", 1, 4),
    "Command Support": ("Dark — Forge Fires", 1, 1),
    "Aviation": ("Kuba — Valkyrie Actual", 1, 4),
}
RULES = [
    ("Respect & conduct", "Treat teammates and other BMG members respectfully. Follow Discord and BMG rules. No harassment, discrimination, threats or deliberate disruption."),
    ("Chain of command", "Forge Actual (Rex) and Forge Bravo (Kahuna) lead FPS. Section leaders coordinate their sections. A/ Team Leaders stand in as needed, without inheriting a permanent radio callsign."),
    ("Operations", "Follow mission briefings, maintain disciplined comms, cooperate with teammates and uphold fair-play standards. Real-life obligations come first; communicate absences when possible."),
    ("Contracts & credits", "FPS credits are fictional campaign currency, not USD. Success pays 100% of agreed fees; legitimate failure pays 50% rounded UP; pending or void contracts pay zero. Shop purchases require Command approval."),
    ("Reputation", "FPS reputation scoring remains DRAFT until approved by Forge Command. Do not treat draft penalties as official."),
    ("Motto", "Forged into Soldiers."),
]

intents = discord.Intents.default()
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
    entries = [(name, values) for name, values in ROSTER.items()
               if not section or section.lower() in name.lower()]
    if not entries:
        return await answer(interaction, "No matching FPS section.")
    try:
        ws = sheet().worksheet("Personnel Dashboard")
        latest = ws.get("A11:D17")
        names = list(ROSTER)
        for index, row in enumerate(latest[:7]):
            if len(row) > 2 and index < len(names):
                name = names[index]
                details, count, cap = ROSTER[name]
                ROSTER[name] = (details, int(float(row[2])), int(float(row[1])))
        entries = [(name, ROSTER[name]) for name, _ in entries]
    except Exception as exc:
        log.warning("Roster using snapshot: %s", exc)
    lines = [f"**{name} — {assigned}/{capacity}**\n{description}" for name, (description, assigned, capacity) in entries]
    await answer(interaction, "\n\n".join(lines), private=False)


@bot.tree.command(name="treasury", description="Display live FPS treasury balance (Command only)")
async def treasury(interaction: discord.Interaction):
    if not is_command(interaction):
        return await answer(interaction, "FPS Command access required.")
    try:
        value = sheet().worksheet("FPS Treasury").acell("C11").formatted_value
        await answer(interaction, f"**FPS Treasury:** {value}", private=True)
    except Exception as exc:
        log.warning("Treasury sheet error: %s", exc)
        await answer(interaction, "Google Sheets is not configured or temporarily unavailable.")


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


@bot.tree.command(name="reputation", description="Show proposed FPS reputation score and tier")
async def reputation(interaction: discord.Interaction):
    try:
        ws = sheet().worksheet("Reputation Meter")
        score = ws.acell("C6").formatted_value
        tier = ws.acell("E6").formatted_value
        await answer(interaction, f"**FPS Reputation (DRAFT)** — {score}/100, {tier}.\nPoint rules require Forge Command approval.", private=False)
    except Exception as exc:
        log.warning("Reputation sheet error: %s", exc)
        await answer(interaction, "Reputation is DRAFT. Google Sheets is not available yet.")


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


if __name__ == "__main__":
    if not TOKEN or TOKEN == "SET_PRIVATELY_IN_HOST":
        raise SystemExit("Set DISCORD_TOKEN as a private hosting environment variable first.")
    bot.run(TOKEN)
