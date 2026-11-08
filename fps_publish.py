"""Manual, read-only publications for Forgepoint Security Discord channels.

The Master Sheet is authoritative. No polling, sheet writes, channel creation,
deletion of human messages, or broad Discord administrator permissions.
"""
import asyncio
import logging
from collections import defaultdict

import discord
from discord import app_commands
from fps_reputation_ui import score_number, reputation_bar, embed_color

log = logging.getLogger("fps.publish")
TEAL = 0x137D73
MAX_FIELD = 1000
MARKER_PREFIX = "FPS_MANUAL_PUBLISH_V1:"
LINK_ROOT = "https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={gid}"
SOURCE_IDS = {
    "roster": 1935550756,
    "chain": 401447990,
    "shop": 297848856,
    "contracts": 1295523985,
    "reputation": 205312977,
    "boc": 1726102226,
}


def value(row, col):
    """Read padded or unpadded gspread rows safely (0-based column)."""
    if row is None or len(row) <= col:
        return ""
    return str(row[col]).strip()


def link(sheet_id, name):
    return LINK_ROOT.format(sheet_id=sheet_id, gid=SOURCE_IDS[name])


def embed_base(title, description, marker):
    e = discord.Embed(title=title[:256], description=description[:4000],
                      color=TEAL, timestamp=discord.utils.utcnow())
    e.set_footer(text="FPS • manually refreshed • " + marker)
    return e


def field(e, title, body):
    title = str(title).strip() or "Information"
    body = str(body).strip() or "—"
    if len(e.fields) >= 25:
        return
    # Stay below Discord's 1024-character field limit and 6000-character
    # total embed limit; prefer a source link over a broken/partial post.
    room = max(0, min(MAX_FIELD, 5500 - len(e) - len(title)))
    if room < 30:
        return
    e.add_field(name=title[:245], value=body[:room], inline=False)


def build_roster(workbook, sheet_id, marker):
    dash = workbook.worksheet("Personnel Dashboard")
    counts = dash.get("A11:D17")
    totals = dash.get("A6:G6")
    members = workbook.worksheet("Master Roster").get("A7:H46")
    by_team = defaultdict(list)
    for r in members:
        team, nickname = value(r, 0), value(r, 2)
        if team and nickname:
            label = nickname
            if value(r, 3):
                label += " — " + value(r, 3)
            if "A/" in value(r, 4) and not value(r, 3):
                label += " (A/)"
            by_team[team].append(label)
    assigned = value(totals[0], 3) if totals else "?"
    total = value(totals[0], 0) if totals else "?"
    e = embed_base("👥 FPS | COMPANY ROSTER",
                   "**{}/{} assigned** • Live roster totals from the Master Sheet.\n"
                   "For vacancies and personal status, see the Personnel Dashboard.".format(assigned, total),
                   marker)
    for r in counts:
        name = value(r, 0)
        if not name:
            continue
        capacity = value(r, 1) or "?"
        num = value(r, 2) or "0"
        participants = "\n".join("• " + m for m in by_team.get(name, []))
        field(e, "{} — {}/{}".format(name.upper(), num, capacity),
              participants or "No members assigned")
    field(e, "LIVE SOURCE", "[Personnel Dashboard]({})".format(link(sheet_id, "roster")))
    return e


def build_chain(workbook, sheet_id, marker):
    ws = workbook.worksheet("Chain of Command")
    lines = ws.get("A33:H39")
    if len(lines) < 7:
        raise ValueError("Command matrix missing: Chain of Command A33:H39")
    e = embed_base("🏛️ FPS | CHAIN OF COMMAND",
                   "Forge Command has overall authority. Team leaders lead their respective sections; "
                   "Command Support coordinates support without taking command of Aviation. "
                   "Leader callsigns belong to the position, not the person.",
                   marker)
    for r in lines:
        team = value(r, 0)
        person = value(r, 3)
        responsibility = value(r, 6)
        if team:
            field(e, team.upper(), "**{}**\n{}".format(person or "Vacant", responsibility))
    field(e, "LIVE SOURCE", "[Chain of Command]({})".format(link(sheet_id, "chain")))
    return e


def build_shop(workbook, sheet_id, marker):
    rows = workbook.worksheet("Catalog").get("A7:G54")
    groups = defaultdict(list)
    for r in rows:
        if value(r, 0).startswith("FPS-") and value(r, 3):
            section = value(r, 1) or "Other"
            line = "`{}` {} — **{}**".format(value(r, 0), value(r, 3), value(r, 4))
            groups[section].append(line)
    if not groups:
        raise ValueError("Catalog is empty. No shop post was changed.")
    e = embed_base("🛒 FPS | EQUIPMENT SHOP",
                   "Company **CR** only (no real-money conversion). "
                   "Paid upgrades require Forge Command approval. "
                   "Standard issue remains FREE in #standard-equipment.",
                   marker)
    for section, lines in groups.items():
        block = ""
        count = 1
        for line in lines:
            proposed = block + ("\n" if block else "") + line
            if len(proposed) > 920 and block:
                field(e, "{}{}".format(section.upper(), " (cont.)" if count > 1 else ""), block)
                block = line
                count += 1
            else:
                block = proposed
        if block:
            field(e, "{}{}".format(section.upper(), " (cont.)" if count > 1 else ""), block)
    field(e, "LIVE SOURCE", "[Equipment Catalog]({})".format(link(sheet_id, "shop")))
    return e


def build_contracts(workbook, sheet_id, marker):
    rows = workbook.worksheet("Contracts").get("A7:J106")
    actual = [r for r in rows if value(r, 1) and value(r, 5)]
    e = embed_base("📋 FPS | CONTRACT REGISTER",
                   "Recent recorded campaign contracts. Entries and payment calculations come from "
                   "the Master Sheet. Success pays 100%; legitimate failure pays 50%, rounded up; "
                   "Pending/Void pays 0.",
                   marker)
    if not actual:
        field(e, "STATUS", "No contracts recorded yet.")
    for r in actual[-8:][::-1]:
        label = "{} • {}".format(value(r, 1), value(r, 5))
        paid = value(r, 7) or "0"
        contractor = value(r, 2) or "Hiring faction not recorded"
        objective = value(r, 3) or "Objective not recorded"
        field(e, label, "**Client:** {}\n**Objective:** {}\n**Payout:** {} CR".format(
            contractor[:140], objective[:220], paid.replace(" CR", "")))
    field(e, "LIVE SOURCE", "[Contract Register]({})".format(link(sheet_id, "contracts")))
    return e


def build_reputation(workbook, sheet_id, marker):
    row = workbook.worksheet("Reputation Meter").get("A6:G6")
    if not row:
        raise ValueError("Reputation Meter status row is empty")
    r = row[0]
    score = score_number(value(r, 2))
    tier, outlook = value(r, 4) or "Unassigned", value(r, 6)
    e = embed_base("📈 FPS | REPUTATION — OFFICIAL",
                   "**Forge Command-approved reputation system.** Completed, approved "
                   "campaign events move the company score from 0 to 100. Higher reputation "
                   "improves hiring opportunities; it does **not** multiply credit payouts.",
                   marker)
    e.color = embed_color(score)
    field(e, "COMPANY REPUTATION",
          reputation_bar(score) + "\n**{} / 100**  •  **{}**".format(score, tier))
    if outlook:
        field(e, "HIRING OUTLOOK", outlook)
    field(e, "SCORING QUICK REFERENCE",
          "Primary objective **+5** • Secondary **+2** • One client bonus **+1 to +3**\n"
          "Contract failure **−5** • Abandonment **−8** • Enemy buyout/betrayal **−25**\n"
          "Other violations and avoidable losses use the approved event schedule. "
          "Each event must be logged and approved by Forge Command.")
    field(e, "LIVE SOURCE", "[Reputation Meter]({})".format(link(sheet_id, "reputation")))
    return e


def build_boc(workbook, sheet_id, marker):
    rows = workbook.worksheet("BOC - Basic Operator Course").get("A9:E13")
    if len(rows) < 5:
        raise ValueError("Basic Operator Course timetable missing")
    e = embed_base("🎖️ FPS | BASIC OPERATOR COURSE (BOC)",
                   "**30 minutes MAXIMUM.** Five quick training blocks; no hazing, lengthy boot camp, "
                   "or written exam. An experienced operator may complete it sooner.",
                   marker)
    for r in rows:
        timer, mins, title, lesson = (value(r, j) for j in (0, 1, 2, 3))
        if title:
            field(e, "{} — {} min".format(title, mins), "{}\n*{}*".format(lesson[:650], timer))
    field(e, "COMPLETION", "Know your team leader, communicate briefly, understand free issue "
                        "and company credits, and finish a short in-game team exercise. "
                        "If someone struggles, coach them and retry.")
    field(e, "LIVE SOURCE", "[Full BOC Guide]({})".format(link(sheet_id, "boc")))
    return e


def build_rules(_unused, _sheet_id, marker, rules):
    e = embed_base("📜 FPS | COMPANY RULES",
                   "Respect teammates, observe BMG/Discord rules, follow mission leadership, "
                   "and communicate. The full rulebook is summarized below.",
                   marker)
    for title, text in rules:
        field(e, title, text)
    return e


def register_publishing(bot, get_sheet, is_command, reply, rules, sheet_id):
    """Register publish and notice slash commands before the bot's first tree sync."""
    lock = asyncio.Lock()
    specs = (
        ("publish_roster", "company-roster", build_roster, "Refresh the FPS personnel roster"),
        ("publish_chain", "chain-of-command", build_chain, "Refresh the FPS chain of command"),
        ("publish_shop", "equipment-shop", build_shop, "Publish live shop prices and upgrades"),
        ("publish_contracts", "contracts", build_contracts, "Publish the latest recorded contracts"),
        ("publish_reputation", "reputation", build_reputation, "Publish the official FPS reputation meter"),
        ("publish_boc", "recruitment", build_boc, "Publish the 30-minute recruit orientation"),
        ("publish_rules", "rules", None, "Publish the FPS rules reference"),
    )

    async def do_publish(interaction, target, builder):
        if not interaction.guild or not is_command(interaction):
            return await reply(interaction, "FPS Command or Discord administrator access required.")
        channel = discord.utils.get(interaction.guild.text_channels, name=target)
        if channel is None:
            return await reply(interaction, "Target channel #{} is missing.".format(target))
        me = interaction.guild.me
        if me is None:
            return await reply(interaction, "Can't verify bot permissions.")
        perm = channel.permissions_for(me)
        if not all((perm.view_channel, perm.send_messages, perm.embed_links, perm.read_message_history)):
            return await reply(interaction, "Missing View/Send/Embed/Read permission in #{}.".format(target))

        # Avoid putting treasury or leadership material where outsiders can see it.
        # These publications have no privileged finance or staff-only details.
        await interaction.response.defer(ephemeral=True, thinking=True)
        marker = MARKER_PREFIX + target
        try:
            if builder is None:
                new_embed = build_rules(None, sheet_id, marker, rules)
            else:
                new_embed = await asyncio.to_thread(lambda: builder(get_sheet(), sheet_id, marker))
        except Exception:
            log.exception("Publication source read failed: %s", target)
            return await reply(interaction, "Couldn't read source data. Nothing was posted or changed.")

        try:
            async with lock:
                existing = None
                async for msg in channel.history(limit=250):
                    if msg.author.id == bot.user.id and any(
                        MARKER_PREFIX + target in (embed.footer.text or "")
                        for embed in msg.embeds
                    ):
                        existing = msg
                        break
                if existing:
                    posted = await existing.edit(embed=new_embed,
                        allowed_mentions=discord.AllowedMentions.none())
                    outcome = "Updated"
                else:
                    posted = await channel.send(embed=new_embed,
                        allowed_mentions=discord.AllowedMentions.none())
                    outcome = "Published"
                if perm.manage_messages and not posted.pinned:
                    try:
                        await posted.pin(reason="FPS permanent information reference")
                    except discord.HTTPException:
                        log.warning("Could not pin %s publication", target)
            await reply(interaction, "✅ {} {}. No spreadsheet data was changed.".format(
                outcome, channel.mention))
        except discord.HTTPException:
            log.exception("Discord publication failed in %s", target)
            await reply(interaction, "Discord couldn't post the update; check the bot permissions.")

    for command_name, channel_name, builder, description in specs:
        def command_factory(dest=channel_name, build=builder):
            async def callback(interaction: discord.Interaction):
                await do_publish(interaction, dest, build)
            return callback
        callback = command_factory()
        callback.__name__ = command_name
        bot.tree.command(name=command_name, description=description)(callback)

    @bot.tree.command(name="post_notice", description="Preview or post a company announcement or operation notice")
    @app_commands.describe(channel="Choose a company notice channel",
                           text="Announcement content; no automatic pings",
                           confirm="False previews; True publishes a new notice")
    @app_commands.choices(channel=[
        app_commands.Choice(name="Company announcements", value="announcements"),
        app_commands.Choice(name="Operations", value="operations"),
    ])
    async def post_notice(interaction: discord.Interaction, channel: app_commands.Choice[str],
                          text: str, confirm: bool = False):
        if not interaction.guild or not is_command(interaction):
            return await reply(interaction, "FPS Command or Discord administrator access required.")
        message = text.strip()
        if not message or len(message) > 1400:
            return await reply(interaction, "Provide 1–1400 characters of announcement text.")
        dest = discord.utils.get(interaction.guild.text_channels, name=channel.value)
        if dest is None:
            return await reply(interaction, "The requested channel was not found.")
        if not confirm:
            return await reply(interaction, "PREVIEW — nothing posted to #{} yet:\n\n{}\n\n"
                               "Re-run with confirm:true to publish.".format(channel.value, message))
        me = interaction.guild.me
        perms = dest.permissions_for(me) if me else None
        if not perms or not all((perms.view_channel, perms.send_messages, perms.embed_links)):
            return await reply(interaction, "The bot can't post in that channel.")
        e = discord.Embed(title="📢 FPS | {}".format(
            "ANNOUNCEMENT" if channel.value == "announcements" else "OPERATIONS NOTICE"),
            description=message, color=TEAL, timestamp=discord.utils.utcnow())
        e.set_footer(text="Issued by {}".format(interaction.user.display_name)[:200])
        try:
            await dest.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
            return await reply(interaction, "✅ Notice posted in {}.".format(dest.mention))
        except discord.HTTPException:
            log.exception("Notice publish failed")
            return await reply(interaction, "Couldn't post that notice; check channel permissions.")
