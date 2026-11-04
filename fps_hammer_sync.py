"""Admin-confirmed Discord FPS Hammer role -> Google Sheets roster reconciliation.

Never remove people, change fixed billets, exceed the seven-seat section cap,
or rely on incomplete Discord member caches.
"""
import asyncio
import logging
import re
import unicodedata

import discord
from discord import app_commands

log = logging.getLogger("fps.hammer_roster_sync")
HAMMER_ROLE = "FPS Hammer"
SHEET_NAME = "Hammer Roster"
FIRST_ROW = 7
LAST_ROW = 13


def normalize(value):
    return "".join(
        character for character in unicodedata.normalize("NFKC", value or "").casefold()
        if character.isalnum()
    )


def aliases(member):
    values = (
        member.name,
        getattr(member, "global_name", None),
        member.nick,
        member.display_name,
    )
    return {normalize(item) for item in values if item and normalize(item)}


def read_roster(get_sheet):
    """Read in a worker thread; return row values and other section nicknames."""
    workbook = get_sheet()
    ws = workbook.worksheet(SHEET_NAME)
    raw = ws.get("A7:I13")
    slots = []
    for index in range(LAST_ROW - FIRST_ROW + 1):
        row = list(raw[index]) if index < len(raw) else []
        row.extend([""] * (9 - len(row)))
        slots.append({
            "number": FIRST_ROW + index,
            "slot": row[0],
            "nickname": row[1].strip(),
            "notes": row[8],
        })
    if any(item["slot"] != "HMR-{:02d}".format(i + 1)
           for i, item in enumerate(slots)):
        raise ValueError("The Hammer roster slot IDs no longer match HMR-01–07.")

    source = workbook.worksheet("Master Roster").get("A7:C46")
    others = {
        normalize(row[2]): (row[0], row[2])
        for row in source if len(row) > 2 and row[0] != "Hammer" and row[2]
    }
    return slots, others


def plan_assignments(members, slots, other_sections):
    assigned = []
    to_add = []
    in_other_team = []
    duplicates = []

    names_taken = {normalize(x["nickname"]) for x in slots if x["nickname"]}
    ids_taken = {}
    for slot in slots:
        match = re.search(r"Discord ID:\s*(\d+)", slot["notes"])
        if match:
            ids_taken[match.group(1)] = slot

    remaining = [item for item in slots if not item["nickname"]]
    for member in sorted(members, key=lambda x: (x.display_name.casefold(), x.id)):
        match_set = aliases(member)
        current = next(
            (slot for slot in slots if slot["nickname"] and
             normalize(slot["nickname"]) in match_set),
            None,
        )
        current = ids_taken.get(str(member.id), current)
        if current is not None:
            assigned.append((member, current))
            continue

        other_match = next(
            (other_sections[a] for a in match_set if a in other_sections), None
        )
        if other_match:
            in_other_team.append((member, other_match[0]))
            continue

        proposed_name = member.display_name.strip() or member.name
        if normalize(proposed_name) in names_taken:
            duplicates.append(member)
            continue
        names_taken.add(normalize(proposed_name))
        to_add.append((member, proposed_name))

    if len(to_add) > len(remaining):
        return assigned, [], in_other_team, duplicates, (
            "Hammer has {} vacant slots but {} additional members hold FPS Hammer. "
            "No changes made; reallocate/remove surplus roles or authorize a new cap."
        ).format(len(remaining), len(to_add))

    planned = [(member, label, slot) for (member, label), slot in zip(to_add, remaining)]
    return assigned, planned, in_other_team, duplicates, None


def commit_assignments(get_sheet, intended, preexisting):
    """Double-check the roster hasn't changed; write exactly three fields/seat."""
    workbook = get_sheet()
    ws = workbook.worksheet(SHEET_NAME)
    current = ws.get("A7:I13")
    snapshot = []
    for index in range(LAST_ROW - FIRST_ROW + 1):
        row = list(current[index]) if index < len(current) else []
        row.extend([""] * (9 - len(row)))
        snapshot.append((row[0], row[1].strip()))
    if snapshot != preexisting:
        raise ValueError("The Hammer roster changed during the preview. Run the command again.")

    payload = []
    for member, nickname, slot in intended:
        row = slot["number"]
        payload.extend([
            {"range": "B{}".format(row), "values": [[nickname]]},
            {"range": "F{}".format(row), "values": [["Active"]]},
            {"range": "I{}".format(row), "values": [[
                "Assigned from FPS Hammer Discord role; reports to Freedlund "
                "(Hammer Actual). Specialty listed in column D remains "
                "provisional until Freedlund confirms it. Discord account: "
                "{} (Discord ID: {}).".format(member.name, member.id)
            ]]},
        ])
    if payload:
        ws.batch_update(payload, value_input_option="RAW")


def register_hammer_sync(bot, is_admin, reply, get_sheet, guild_id=0):
    sync_lock = asyncio.Lock()

    @bot.tree.command(
        name="sync_hammer",
        description="Preview or add members holding FPS Hammer to the 7-slot roster",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        confirm="False previews proposed seats; True adds missing Hammer members to Google Sheets",
    )
    async def sync_hammer(interaction: discord.Interaction, confirm: bool = False):
        guild = interaction.guild
        if guild is None or (guild_id and guild.id != guild_id):
            return await reply(interaction, "Run this in the FPS Discord server.")
        if not is_admin(interaction):
            return await reply(
                interaction, "Only a Discord server administrator can synchronize the Hammer roster."
            )

        if not bot.intents.members:
            return await reply(
                interaction,
                "Discord member listing is not enabled. First enable the "
                "**Server Members Intent** in the Discord Developer Portal "
                "(Bot → Privileged Gateway Intents), set the Northflank variable "
                "**FPS_MEMBER_SYNC_ENABLED=1**, and redeploy/restart the bot. "
                "No roster changes made.",
            )
        role = discord.utils.get(guild.roles, name=HAMMER_ROLE)
        if role is None:
            return await reply(interaction, "FPS Hammer role not found. No changes made.")

        await interaction.response.defer(ephemeral=True, thinking=True)
        async with sync_lock:
            try:
                # Accurate full guild member list, not the potentially partial cache.
                discord_members = []
                async for member in guild.fetch_members(limit=None):
                    if not member.bot and any(r.id == role.id for r in member.roles):
                        discord_members.append(member)
            except (discord.Forbidden, discord.HTTPException, discord.ClientException):
                log.exception("Could not fetch the full FPS member list")
                return await reply(
                    interaction,
                    "Discord would not provide the full member list. Check "
                    "**Server Members Intent** in the Discord Developer Portal "
                    "and Northflank FPS_MEMBER_SYNC_ENABLED. No changes made.",
                )

            if not discord_members:
                return await reply(
                    interaction,
                    "No non-bot users with FPS Hammer were returned. "
                    "No roster changes made.",
                )
            try:
                slots, other_sections = await asyncio.to_thread(read_roster, get_sheet)
            except Exception:
                log.exception("Failed to read Hammer roster")
                return await reply(
                    interaction, "Can't read the FPS Master Sheet. No roster changes made."
                )

            known, planned, elsewhere, duplicates, overflow = plan_assignments(
                discord_members, slots, other_sections
            )

            lines = [
                "**FPS HAMMER ROLE → ROSTER {}**".format(
                    "PREVIEW" if not confirm else "SYNC"
                ),
                "Discord members with FPS Hammer: **{}**. "
                "Already matched in Hammer: **{}**. "
                "Available roster slots: **{}**.".format(
                    len(discord_members), len(known),
                    sum(not slot["nickname"] for slot in slots),
                ),
            ]
            for member, nickname, slot in planned:
                lines.append(
                    "• {} → **{}** ({}, provisional duty)".format(
                        member.mention, slot["slot"], nickname
                    )
                )
            if not planned:
                lines.append("No new Hammer roster entries planned.")
            if elsewhere:
                lines.append("**Blocked cross-team matches:** " + ", ".join(
                    "{} ({} roster)".format(m.mention, t) for m, t in elsewhere
                ))
            if duplicates:
                lines.append("**Ambiguous duplicate names:** " + ", ".join(
                    member.mention for member in duplicates
                ))
            if overflow:
                lines.append("**Over capacity:** " + overflow)

            if elsewhere or duplicates or overflow:
                lines.append(
                    "No changes made. Resolve the listed conflicts and retry."
                )
                return await reply(interaction, "\n".join(lines))

            if not confirm:
                lines.append(
                    "Existing Freedlund / Stratt / Lanal billets are never overwritten. "
                    "New members fill only vacant seats; specialty assignments "
                    "are provisional. No one is removed if their role changes."
                )
                lines.append("Run **/sync_hammer confirm:true** to apply.")
                return await reply(interaction, "\n".join(lines))

            if not planned:
                return await reply(
                    interaction, "✅ All recognized FPS Hammer role members are already on the roster."
                )

            before = [(item["slot"], item["nickname"]) for item in slots]
            try:
                await asyncio.to_thread(
                    commit_assignments, get_sheet, planned, before
                )
            except Exception:
                log.exception("Failed to write Hammer roster")
                return await reply(
                    interaction,
                    "⚠️ Roster update was not confirmed. Check the Hammer Roster "
                    "tab before retrying in case Sheets applied a partial change.",
                )
            lines.append(
                "✅ Added **{}** members to Hammer under **Freedlund**. "
                "Existing roles, billet titles, and other team rosters were not changed. "
                "Run /publish_roster to refresh Discord's roster post.".format(
                    len(planned)
                )
            )
            return await reply(interaction, "\n".join(lines))
