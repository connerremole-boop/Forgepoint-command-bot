# Forgepoint Command Bot — Starter Deployment

**Status:** LIVE on Northflank (according to the successful Discord tests). The bot reads its data from the FPS Google Sheet and does not write to it. Currently deployed commands: `/setup_fps`, `/roster`, `/treasury`, `/shop`, `/reputation`, `/contracts`, and **`/publish_equipment`**. The current integration uses manual publication, not automatic background updates.

## Old Guys-aligned shop (weapon shortlist; Fridgy confirmation pending)

The FPS Master Sheet **Catalog** is now the authoritative Old Guys-aligned V2 shortlist, while the original FPS credit system remains intact. The gun options follow Old Guys/RHS/WCS/Nasty/B59-style workshop content, but **the exact FPS server arsenal has not been confirmed**; do not treat a listed weapon as installed until Fridgy verifies the server mod configuration. No Old Guys mod files were modified.

**Infantry (Anvil & Hammer):** FPS-001 M4A1 CQBR (4 CR); FPS-002 HK416A5 (6); FPS-003 Mk 17 / SCAR-H (7); FPS-004 M203 (6); FPS-005 Nasty M1014 (5); FPS-006 Nasty SR-25 (10); new FPS-049 **AK — all approved variants (5 CR)**. All AK variants use **one SKU, one price, one unlock**, never per-variant IDs.

**Raven STA:** FPS-013 M38 SDMR (8 CR); FPS-014 Nasty SR-25 (10); FPS-015 Nasty420 M700 (12); FPS-016 Nasty OSV-96 (15). **Titan:** first M249 remains free, additional M249 (5 CR), M240B (8), B59 Mk 48 (10), M72 LAW (8), Mk 153 SMAW (15). Other packages, vehicles, nonweapon upgrades, and section restrictions remain as before.

**Integration:** The live `/shop` command and `/publish_shop` use `Catalog!A7:G55`, including FPS-049. `Purchases!C7:E106` lookup formulas now include the new Catalog row so the AK SKU resolves and deducts CR correctly when approved purchases are logged. Publish the new shop with `/publish_shop` after Northflank deploys this commit. This bot only reads Sheets; it does not write purchases automatically.

## FPS Medic — specialist role

**`FPS Medic`** is now included in Forgepoint's standard role list and can be assigned by the existing `/assign_role` command alongside FPS Member, FPS Anvil/Hammer/etc., and FPS Team Leader. It is a **cross-team specialty**, not a new section. The role does **not** grant access to private team chats, change command authority, or confer extra Discord permissions; medics still need the appropriate team role. Its role color is left unset so the member's unique team color is shown in chat when the team role is positioned highest.

After the updated GitHub code deploys on Northflank, a Discord server administrator can run **`/setup_fps confirm:false`** and check that `FPS Medic` is the only missing role, then run **`/setup_fps confirm:true`** to create it. The setup routine only creates missing roles/channels and does not replace existing ones. If the preview lists any other missing channels or categories, it is important to review them before confirming, because setup would create those too.

To assign it, run `/assign_role member:@Member role:@FPS Medic` (or choose the Medic role as one of up to five selected roles). The role does not alter the Google Sheets roster.

## Change Anvil Team Leader from Wolf to Bama (AlabamianFox)

The existing **Anvil Roster ANV-01** (Anvil Actual) and its linked Master Roster, Chain of Command, and succession views now identify **Bama**, replacing **Wolf** after inactivity. The permanent callsign belongs to the position, not the player. Bama's correct Discord username is **AlabamianFox** (not AlabamaFox).

**Admin-only Discord role handover:** `/replace_anvil_lead wolf:<select Wolf> bama:<select AlabamianFox> confirm:false` previews the exact selected accounts and FPS role changes. Re-run with `confirm:true` to grant the new Anvil lead any missing **FPS Member**, **FPS Anvil**, and **FPS Team Leader** roles, then revoke those three scoped FPS roles from the outgoing Wolf account. The command requires a selected Bama account whose actual Discord username is `AlabamianFox`; Wolf must currently hold FPS Anvil and FPS Team Leader. The bot needs **Manage Roles** and its top role must be above both members and the three roles. It refuses to copy a role that has acquired elevated Discord permissions.

**Safety:** The command does not clone unrelated/privileged Discord roles, grant FPS Command, change the Sheet again, or silently assume which Discord account is Wolf. Preview explicitly lists any other Wolf roles left untouched. Verify no privileged access remains on Wolf if he had other roles. If Wolf has already left the server, use `/assign_role` for Bama and inspect/remediate any lingering Wolf role/member separately. After live role changes, run `/publish_roster` and `/publish_chain`.

**Not automatically executed:** Committing this code does not mutate live Discord roles. Redeploy Northflank, then have a server admin execute the preview and confirmed command.

## Sync FPS Hammer Discord role members into the roster

**New admin-only command:** `/sync_hammer` imports all non-bot Discord members who have the existing `FPS Hammer` role into vacant **Hammer Roster** slots in the FPS Master Sheet. All are subordinate to **Freedlund (Hammer Actual)**. It does **not** change Discord roles, create new slots, increase Hammer's seven-person cap, or alter existing assigned billets (including Freedlund HMR-01, Stratt HMR-02, or Lanal HMR-06).

**One-time setup (required for Discord's complete member list):**

1. In the [Discord Developer Portal](https://discord.com/developers/applications), select the Forgepoint Command application, go to **Bot → Privileged Gateway Intents**, and turn on **Server Members Intent**.
2. In Northflank, set `FPS_MEMBER_SYNC_ENABLED=1` on the bot service and deploy/restart. **Do not set the environment variable until the Discord Developer Portal intent is enabled**, or Discord may reject the bot's gateway connection.
3. Ensure the bot's configured Google service account has **Editor** access to the existing FPS Master Sheet. Previous public commands only needed to read it; this command needs write access.

**Usage:** First run `/sync_hammer confirm:false` to fetch the complete Discord role membership, compare it to the existing seven Hammer roster slots, and preview every addition. This is read-only. Check that member names and proposed vacant slots are correct; if a Discord nickname differs from the person's known FPS roster nickname, a false duplicate is possible and must be resolved before applying. Then run `/sync_hammer confirm:true` to re-check current role membership and the Sheet, and add the matched candidates.

**Safeguards:** The command rejects cross-team matches, duplicate display names, and over-capacity imports instead of writing an incomplete set. It never overwrites occupied rows and leaves all existing billets unchanged. New members are marked **Active**, not automatically **Available**, and assigned the next vacant seat with a note that the existing billet specialty (Rifleman, Grenadier, Automatic Rifleman, Designated Marksman) is **provisional until Freedlund confirms it**. Discord account IDs are saved in the row's Notes to help later reconciliation. It is safe to rerun: members already present are skipped, and role removals do not automatically dismiss members from the roster.

After successful synchronization run `/publish_roster` to refresh the managed company-roster Discord post. If the bot reports a Sheets permission error, give its Google service account Editor permission and retry after checking the Sheet for any partial update. This command has not been executed in live Discord just by committing the code.

## Private and writable FPS team chats

New admin-only command: `/setup_team_chats`.

- **Preview:** `/setup_team_chats confirm:false` — shows all five channels, their assigned role, and the FPS Command oversight exception. Makes no changes.
- **Apply:** `/setup_team_chats confirm:true` — restricts each team chat's **View Channel**, **Read Message History**, message sending, reactions and thread/chat permissions to the **assigned team role + FPS Command**. The bot retains access to its own server channels. Discord server Administrators can always bypass channel restrictions.
- **Unchanged:** General FPS information, treasury, leadership, Text Channels, Adults Only, all voice channels, and the channels' category placement. No changes to Google Sheets, member role assignments, or previous messages.

| Chat | Members who can see and message |
|---|---|
| `#anvil-team` | FPS Anvil + FPS Command |
| `#hammer-team` | FPS Hammer + FPS Command |
| `#raven-sta` | FPS Raven + FPS Command |
| `#titan-heavy` | FPS Titan + FPS Command |
| `#aviation` | FPS Aviation + FPS Command |

**Important:** Give every team leader their corresponding **team role** (Anvil, Hammer, etc.). Having `FPS Team Leader` **alone** no longer grants access to every section chat. Command members retain an oversight exception. Ordinary Discord admins and the server owner also retain Discord's built-in access. Prior team messages become hidden from people who lose permission, but are not deleted.

Existing member/role-specific channel permission **allows** for unrelated users are cleared to prevent bypassing the new privacy setting. Pre-existing explicit denial exceptions are retained. Running `/setup_readonly` again later preserves team-private visibility and applies **only assigned section + FPS Command** posting access in those channels.

The bot needs **Manage Channels** and **Manage Roles** and must already have permission to edit each channel. This command only modifies the five exact existing text channels, requires an explicit confirmation, and can be safely rerun without intentional duplicate or unrelated changes.

## Read-only FPS channels with role exceptions

New, **opt-in admin-only** command: `/setup_readonly`.

Run `/setup_readonly confirm:false` to preview which channels would be changed and which staff/team roles would be permitted to post. It makes **no changes**. Run `/setup_readonly confirm:true` to apply after checking the list.

**Scope:**
- Every standard text/announcement/forum channel **outside** the exempt categories. This includes uncategorized text channels. Existing channel visibility stays unchanged.
- **Not touched at all:** the `Text Channel` / `Text Channels` category (including decorative punctuation/emoji), the `Adults Only` category, and all voice/stage channels. Thread write permissions on targeted text/forum parent channels are restricted, because Discord threads inherit their parent's permissions.
- **General informational and operations channels:** only `FPS Command` and `FPS Team Leader` may write. `#operations` also permits `FPS Command Support`.
- **Team-specific channels:** Only FPS Command plus the corresponding section role may write: `#anvil-team` → FPS Anvil, `#hammer-team` → FPS Hammer, `#raven-sta` → FPS Raven, `#titan-heavy` → FPS Titan, `#aviation` → FPS Aviation. Visibility is separately controlled by `/setup_team_chats`.
- **`#leadership` and `#company-treasury`:** only `FPS Command` can type (plus Discord administrators by design). **Treasury remains publicly readable if `/setup_appearance` already made it public.** The role-based lock does not alter any View Channel permission or move channels to other categories.

This explicitly denies posting, reactions, slash-command execution, and creating/sending into threads for ordinary members in the affected channels. Regular members can still run `/balance` in an exempt social text channel. Pre-existing member-specific positive posting exceptions and irrelevant-role posting exceptions are cleared so the FPS role rules hold; other read/visibility/management permissions and negative member-specific blocks are preserved. The bot retains permission to publish its information posts. **Discord server administrators always bypass ordinary channel restrictions** and cannot be made read-only through these channel overwrites.

This operation is safe to rerun: it skips channels that already match. It does not touch Sheets, bots' source data, role assignments, voice channels, or existing messages. A server administrator must authorize it and the bot must have **Manage Channels** and **Manage Roles** in all affected channels. If any channel edit is denied, the command reports how many succeeded and which failed so it can be retried.

## Finish the FPS Discord appearance and public treasury

The bot has two new slash commands (requires the new version to deploy from GitHub to Northflank):

1. `/setup_appearance confirm:false` — admin-only preview. Lists all colors, planned channel permission change, and a privacy warning. **No changes.**
2. `/setup_appearance confirm:true` — admin-only apply. Colors existing team roles, makes **only** `#company-treasury` visible and read-only to `@everyone`, then publishes a pinned company-balance snapshot if the bot has Manage Messages. **It does not make other command channels public or alter Google Sheets.**
3. `/publish_treasury` — FPS Command or server admins can rerun it whenever contract income/purchases change. It reads only `FPS Treasury!C11`, updating its existing managed balance post rather than spamming another. Everyone can still use `/balance` in an accessible text channel to get the current live amount.

**Unique team colors (only these six section roles are recolored):**

| Team role | Distinctive chat color |
|---|---|
| FPS Anvil | Blue `#3B82F6` |
| FPS Hammer | Orange `#F97316` |
| FPS Raven | Purple `#A855F7` |
| FPS Titan | Red `#EF4444` |
| FPS Aviation | Cyan `#06B6D4` |
| FPS Command Support | Green `#22C55E` |

Generic `FPS Member` and `FPS Team Leader` roles are intentionally unchanged to avoid overriding individual section colors. Discord displays the color of each member's **highest-positioned colored role**; if an unrelated or higher role also has a color, the relevant section role may need to be positioned higher by a server administrator.

**Treasury permission and placement:** The existing `#company-treasury` stays **within its current FPS COMMAND category**, with a channel-specific override giving `@everyone` **View Channel + Read Message History**, but **not Send Messages**. `#leadership` and the rest of the private command area are not changed. The treasury becomes an **unsynced channel** so its public override will not change the category or sister channels.

**IMPORTANT:** After applying, previous messages in `#company-treasury` will also be visible to all server members. Review its history before using `confirm:true`. The bot needs **Manage Roles** and its highest role above each team role, **Manage Channels** for the treasury, plus **Send Messages** and **Embed Links**; `Manage Messages` is optional for automatic pinning. These commands never create roles or automatically synchronize the Sheets roster.

## One-command role assignment for Kuba (Aviation Lead)

Forgepoint Command now has `/assign_kuba`. **Select Kuba's exact Discord member account** from the slash command user picker; the bot does **not** attempt to guess his Discord identity from a nickname or the Google Sheet.

1. Preview with `/assign_kuba member:@Kuba confirm:false` to check the Discord user and all requested roles without changing anything.
2. Apply with `/assign_kuba member:@Kuba confirm:true`. This grants exactly the **missing** roles from **FPS Member**, **FPS Aviation**, and **FPS Team Leader**.
3. The FPS Aviation role permits entry to the private `#aviation` channel; Team Leader recognizes Kuba's Aviation Lead position. The bot does **not** grant FPS Command, Command Support, or Discord administrative permissions, and does not remove any existing roles.

The command is restricted to FPS Command and Discord server administrators. The bot needs `Manage Roles` and its highest role must be above both the user and roles it manages. If a Discord API operation fails midway, the command reports the roles it added and can safely be repeated; roles already held are skipped. **No Google Sheets data is modified.** The new command becomes available after Northflank redeploys the GitHub main branch.

## Assigning existing Discord roles

**Role commands (no creation of new roles):**

- `/assign_role member:@Person role:@FPS Member role2:@FPS Anvil role3:@FPS Team Leader` — assign **up to five FPS roles at once**. The first `role` is required; `role2` through `role5` are optional. Existing roles are skipped, duplicates are deduplicated, and **all selected roles are checked for permissions before any assignment**.
- `/remove_role member:@Person role:@FPS Hammer` — remove an existing FPS Discord role.

Bulk assignment does **not** automatically remove old team roles; use `/remove_role` for transfers. The bot applies several additions in one command, but Discord processes individual role updates, so a network failure can leave a partial result; check the member's roles if an error is reported.

Both commands are restricted to **FPS Command** or Discord server administrators. They accept only roles from the bot's existing FPS role allowlist: FPS Command, FPS Team Leader, FPS Member, FPS Anvil, FPS Hammer, FPS Raven, FPS Titan, FPS Aviation, and FPS Command Support. **Only a Discord administrator can grant or remove FPS Command itself**, and granting roles with sensitive Discord administrative permissions also requires an administrator. Normal member and section roles can be delegated by FPS Command staff.

The bot needs **Manage Roles** permission and its highest role must be **above the FPS roles** it manages in Server Settings → Roles. Discord role assignments do **not** edit the Google Sheets roster and do **not** automatically remove other team roles. When transferring a member from Anvil to Hammer, assign Hammer and then remove Anvil; separately update the Google Sheets roster to keep published member records in sync. These actions return a private confirmation and keep audit reasons on the Discord role change.

## Public treasury balance for all FPS members

**`/balance`** can be used by **any member of the FPS Discord server**, in any channel where they can use application commands. It posts a normal **public** Discord reply (not an ephemeral one) showing only the live **FPS Treasury!C11** company balance in fictional CR. No Google Sheets edits, individual transactions, purchases, or other private records are disclosed.

The older **`/treasury`** command remains **FPS Command-only** and responds privately. Until `/setup_appearance confirm:true` is run, **`#company-treasury`** keeps its original private permissions. After setup, it becomes publicly readable (but remains read-only for regular members). Regardless, any server member can use `/balance` in a channel they can access.

This update is committed to the GitHub main branch; the connected Northflank service must deploy the latest commit before the slash command appears. If it does not, inspect the Northflank deployment status and logs.

## Official FPS reputation (Forge Command approved)

The 0–100 reputation system is now **OFFICIAL**. It starts at **50 / 100 (Unproven)**. The Master Sheet's **Reputation Meter** is authoritative; its formulas derive the current score from chronological, completed, Forge Command-approved event entries.

Two live Discord views show the numeric score, current tier, hiring outlook, and a color-coded **10-block meter**:
- `/reputation` is a public read-only lookup, available immediately after bot deployment.
- `/publish_reputation` is for FPS Command/admins and publishes or updates the managed post in `#reputation`. Re-run after approved events are entered in Sheets. There is **no background refresh**.

**Approved scoring:** primary objective +5, optional secondary +2, exactly one client bonus +1 to +3 per contract, legitimate failure −5, abandonment −8, and enemy buyout/betrayal −25. Avoidable-loss penalties are −2/−3/−5; contract violations are −5/−8/−10. Don't duplicate a penalty for the same betrayal. The score is clamped from 0 to 100.

**Hiring tiers:** Blacklisted 0+, Unreliable 10+, Questionable 25+, Unproven 40+, Trusted 60+, Elite 75+, Legendary 90+. Better reputation affects contract access and employers' willingness to hire FPS, but **does not multiply CR payouts**. Contract payouts remain 100% on success, 50% rounded up on legitimate failure, and 0 on Void/Pending.

**Recording changes:** enter a date, contract ID, event type, approver, and notes on the Reputation Meter's approved event log, then run `/publish_reputation`. This live bot does **not** implement the old proposed `/reputation_event` write command, and simply setting legacy `ENABLE_REPUTATION_WRITES` flags will not add it.

## Essential channel publisher commands

These commands are **manual** (no background monitoring). They pull fresh data from the already-connected Master Sheet each time, then publish **one bot-authored reference post per channel**. Re-running a command edits its previous managed message, within the most recent 250 channel messages, rather than posting duplicates. Commands are restricted to FPS Command or Discord server Administrators and are **read-only** toward Google Sheets.

| Slash command | Destination channel | Data source / action |
|---|---|---|
| `/publish_equipment` | `#standard-equipment` | Free base loadout + Titan starting M249 |
| `/publish_roster` | `#company-roster` | Personnel Dashboard + Master Roster |
| `/publish_chain` | `#chain-of-command` | Live leadership from Chain of Command |
| `/publish_shop` | `#equipment-shop` | All upgrade prices from Catalog |
| `/publish_contracts` | `#contracts` | Most recent 8 contracts and payouts |
| `/publish_reputation` | `#reputation` | Official 0–100 reputation, 10-block colored meter, and hiring outlook |
| `/publish_boc` | `#recruitment` | Five-block, 30-minute Basic Operator Course |
| `/publish_rules` | `#rules` | Summary of the existing static company rules |
| `/post_notice channel:<announcements or operations> text:<your text> confirm:<false/true>` | `#announcements` or `#operations` | Creates a **new** notice only when `confirm:true`; otherwise shows a private preview |

**Important:** The original setup's first chain-of-command and rules posts are separate from the new managed summaries. The first `/publish_chain` or `/publish_rules` may add one new post. Review the new post and optionally remove the old one manually if redundant. Nothing here deletes channels, roles, human posts, or spreadsheet records.

**Privacy:** The treasury and command leadership channels are not public publisher targets. Use the existing private `/treasury` slash command for financial balances. The bot only pins updates if it has `Manage Messages` in the target channel; granting Administrator permission is unnecessary.

## Publishing standard equipment in Discord

**What it does:** `/publish_equipment` reads **Base Equipment!A6:E13, A18:E18, and A22:A24** from the live FPS Master Sheet, then creates or updates one bot-authored embed in **#standard-equipment**. It includes the free starter loadout, the *one initial M249 for Titan Heavy* rule, shop-policy notes, and a source link. It does **not** spend credits or modify Google Sheets.

**Who can run it:** Discord Administrators or members with the `FPS Command` Discord role. Ordinary members can read the published channel post.

**Phone steps:**
1. In Discord, type `/publish_equipment` anywhere in the FPS server and choose the Forgepoint Command command.
2. The bot privately confirms the publish; everyone with access to `#standard-equipment` sees the single public reference post.
3. When the Base Equipment tab changes, run the *same* command again; it edits its existing message rather than adding duplicates (provided the message is still within the last 250 messages in that channel).
4. **Pinning is optional.** If the bot has Manage Messages permission for that channel, it pins the post. Otherwise a human moderator can pin it manually. **Do not grant Administrator** just for pinning.

**Deployment:** The private `main` branch is linked to **Northflank** and was configured to auto-deploy. New commits will normally redeploy it; check Northflank's deployment logs if the new slash command does not appear. The bot needs its existing `DISCORD_TOKEN`, `DISCORD_GUILD_ID`, and securely mounted Google service-account credentials. Never put keys or tokens in GitHub.

## Original deployment notes (Railway alternative)

## Deploy on Railway (phone-friendly)
1. Connect this private GitHub repository in Railway → New Project → Deploy from GitHub.
2. Use the included `Dockerfile`; Railway will run `python bot.py`.
3. Add private Railway **Variables**:
   - `DISCORD_TOKEN`: copy the token yourself from Discord Developer Portal → Bot. **Never commit/share the token.**
   - `DISCORD_GUILD_ID`: your Discord FPS server ID (Discord Developer Mode → Copy Server ID).
   - `GOOGLE_SHEET_ID`: `1ZH5-ComS-Dv21bRGgM7GZ9SfS1bRcE6QfOXjTqshE6Y` (already has this default).
   - `GOOGLE_SERVICE_ACCOUNT_B64`: optional until setting up live Google Sheets; this is the Base64 of a dedicated Google service account JSON key, kept secret in Railway, and the service account must have Viewer access to the Master Sheet.
4. Deploy and confirm Railway logs show `Logged in as Forgepoint Command`.
5. In Discord, use `/setup_fps confirm:false` before approving `confirm:true`. Only admins can run it. It creates missing channels/roles and never deletes existing ones.
6. The bot role needs **Manage Channels**, **Manage Roles**, **View Channels**, **Send Messages**, **Read Message History**, **Embed Links**; move bot role above FPS roles if role management fails.

**Caution:** Google Sheet write commands, automatic announcements, and recurring synchronization from the original V1 prototype are **not yet deployed in this starter**. Sheet-linked read commands require a Google service account configured in Railway. Reputation rules are **OFFICIAL**, but Sheet updates remain manual; no real-money exchange value is assigned to CR.

---
## Original V1 design notes (planned / bundled separately)
# Forgepoint Security — Command & Management Discord Bot

**FPS Command Bot** is a Python 3.11+ Discord bot for **Forgepoint Security**, the modern PMC unit in the BMG/Arma Reforger campaign. It can scaffold your existing Discord server, publish your unit rules, and use your **existing** Google Sheets workbook as its live source of truth.

This is the **initial functional version**. The full source code, tests, Dockerfile, and sample configuration are included. You must create the Discord application and connect Google Sheets; **no bot has been installed into or run on your server by ChatGPT**.

## Features

| Capability | Command / behavior |
|---|---|
| Server setup | `/setup_fps confirm:false` **previews**; `/setup_fps confirm:true` creates *missing* FPS categories, roles and channels, then publishes first posts |
| Rulebook | Three polished embeds in `#rules`, with operational, conduct and finance policies |
| Command structure | Dynamic chain of command posted to `#chain-of-command` |
| Roster | `/roster section:Hammer` and automatic `#company-roster` snapshot |
| Credits | `/treasury` privately shows real balance from `FPS Treasury!C11` |
| Shops | `/shop section:Anvil & Hammer` displays items/prices from `Catalog` |
| Contracts | `/contracts` shows finalized results; command staff can use `include_pending:true` privately |
| Reputation | `/reputation` displays official score, tier, hiring outlook and visual meter |
| Publish/update | `/publish channel:company-roster` edits the previous bot-authored post; similarly for other info channels |
| Contract writes* | `/contract_add`, `/contract_result` fill only non-formula input cells |
| Purchase writes* | `/purchase` validates Catalog ID, quantity and available CR; preserves formula cells |
| Roster writes* | `/roster_assign`, `/roster_unassign` enforce authorized slot limits and preserve fixed leadership callsigns |
| Reputation writes** | `/reputation_event` adds approved events while preserving sheet formulas; checks duplicate/buyout stacking |

\* Disabled until `ENABLE_SHEETS_WRITES=true`. \** Additionally disabled until `ENABLE_REPUTATION_WRITES=true` because the legacy V1 write functionality was not deployed in the current bot (the reputation policy is now official).

**Command hierarchy:** only Discord server Administrators can run `/setup_fps`; only Discord Administrators or people with the **FPS Command** role can write campaign data. Reading the central treasury is also restricted to FPS Command. The bot does not give anyone server-administrator permissions.

## 1. Create the Discord app (you must do this)

1. Go to **https://discord.com/developers/applications** and create a new application named `Forgepoint Command`.
2. Open **Bot**, create/reset the bot token, and copy it privately into your `.env` file as `DISCORD_TOKEN`. **Never send me your token**, put it in a Google Sheet, or commit it to GitHub.
3. Under **Installation** / **OAuth2**, add the bot to your existing FPS server with `bot` and `applications.commands` scopes.
4. Grant these bot permissions: **Manage Roles**, **Manage Channels**, **View Channels**, **Send Messages**, **Read Message History**, **Embed Links**. You do **not** need to grant the bot `Administrator`, `Kick Members`, or `Ban Members`.
5. In Discord, enable **User Settings → Advanced → Developer Mode**, right-click your FPS server and **Copy Server ID** into `.env` as `DISCORD_GUILD_ID`.
6. Under **Server Settings → Roles**, place the bot's role **above** the FPS roles it will create, so it can assign them. Your existing owner/admin remains in control.

The bot uses slash commands. It doesn't need the privileged **Message Content** or **Server Members** intents for its current functionality.

## 2. Connect YOUR existing Google Sheet

**Current linked workbook:** [Forgepoint Security Master Sheet](https://docs.google.com/spreadsheets/d/1ZH5-ComS-Dv21bRGgM7GZ9SfS1bRcE6QfOXjTqshE6Y/edit)

1. Open **https://console.cloud.google.com/**. Create/select a Google Cloud project.
2. Enable **Google Sheets API** and **Google Drive API** for the project.
3. Under **IAM & Admin → Service Accounts**, create a new service account (for example, `fps-discord-bot`). Create/download a **JSON key** in its **Keys** area.
4. Put the JSON file in the bot folder as `service-account.json` (or update `GOOGLE_SERVICE_ACCOUNT_FILE` to its private path). Do **not** send or upload that JSON to chat/Discord/public repositories.
5. Open your Master Sheet; click **Share**; add the service account's `client_email` from that JSON. Use **Viewer** permissions for read-only use or **Editor** if you will enable bot write commands.
6. The existing spreadsheet ID is already filled in `.env.example`; you don't have to recreate any workbook or copy data.

**Cloud hosting option:** instead of storing the JSON file on a hosted service, provide its Base64-encoded bytes as a private environment variable `GOOGLE_SERVICE_ACCOUNT_B64`. The bot supports both methods (the Base64 env var takes precedence). **Base64 is *not encryption*** — protect that value like a password.

**What is synced from the live Sheet?** All named teams, the 30-slot roster, Stratt as Hammer A/, 4-slot airwing, fixed Actual callsigns, item prices, contracts, CR treasury, and reputation read from the current workbook. The bot **does not** convert CR to real-world dollars.

## 3. Run it locally

Install **Python 3.11 or newer**, then, in this folder:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your private configuration file from the template:

```bash
# Linux/macOS:
cp .env.example .env
# Windows PowerShell:
# Copy-Item .env.example .env
```

Edit `.env` with your Discord token and server ID. Keep both write switches `false` initially. Run:

```bash
python bot.py
```

When online, open Discord and type:

```text
/setup_fps confirm:false
/setup_fps confirm:true
/roster section:Hammer
/treasury
/shop section:Anvil & Hammer
/reputation
```

**Set up preview first.** Confirmed setup only **creates missing channels and roles**; it does not delete existing ones or overwrite existing channel permission settings. If a channel with the desired name already exists in another category, setup skips it rather than duplicating it. Initial posts are saved in `data/state.json` so running `/publish` edits the bot's own messages instead of reposting them.

### Role assignment

The created roles are: FPS Command, FPS Team Leader, FPS Member, and the five FPS section roles plus FPS Command Support. **Assign yourself and Kahuna the FPS Command role manually in Discord Server Settings** (or use your Administrator authority). This code never guesses Discord identities from spreadsheet nicknames and never automatically reassigns the current roster to Discord accounts.

For subsequent roster additions, a Command user can run `/roster_assign` with an optional `discord_member` selection to grant that person the appropriate FPS roles. If an owner manually removes a member, review their Discord roles separately. The bot will not delete roles or existing channels.

## 4. Switch on approved campaign actions when ready

After testing the bot against the live workbook, back up the Master Sheet and change:

```env
ENABLE_SHEETS_WRITES=true
ENABLE_REPUTATION_WRITES=false
```

Then restart the bot. Command users can register contracts, approve purchases, or add members through Discord. **The spreadsheet remains the master record**; the bot only writes to its existing input columns. The sheet formulas calculate contract payouts and treasury balances:

- Success = 100% of agreed CR fee.
- Failure = 50% rounded **UP** (15 → 8 CR; 25 → 13 CR).
- Void/Pending = 0 CR.
- FPS credits have **no USD conversion**.

The reputation system is now **OFFICIAL**, starting at **50/100**, with an approved **−25** enemy buyout/betrayal penalty. The original V1 `/reputation_event` write command is not part of this live bot; do not enable legacy flags expecting it to appear. Log approved events directly into the Reputation Meter Sheet and refresh the public post with `/publish_reputation`.

**Important:** The bot validates bot-initiated actions but cannot prevent a human from editing the same spreadsheet row at the same instant, cannot guarantee cash accounting when external bots write concurrently, and cannot enforce every in-campaign pricing restriction. Keep an approval workflow for purchases/contracts. The existing workbook has **100 preformatted contract, purchase and reputation-log rows**. Extend its formulas before adding more.

## 5. Host it 24/7

Run `python bot.py` on a computer that stays online, or deploy it as a **worker** on a host supporting always-on Python apps or Docker. A basic `Dockerfile` is included. Example local Docker run:

```bash
docker build -t fps-command-bot .
docker run --restart unless-stopped --env-file .env \
  -v "$(pwd)/service-account.json:/app/service-account.json:ro" \
  -v "$(pwd)/data:/app/data" \
  fps-command-bot
```

For cloud deployment, set the bot token, server ID, sheet ID, and **private** service-account Base64 value as secrets/environment variables. Mount `/app/data` as persistent storage so stored message IDs survive restarts. The bot **does not run 24/7 from this ChatGPT conversation**.

## Setup safety & known limits

- **No external EDWIN integration yet.** If Clifford provides an API, we can add it later without claiming to control BMG servers now.
- **Not automatic live message push:** slash reads are live; use `/publish` to refresh channel snapshot embeds after Sheet edits. Automatic scheduling/webhooks can be added later.
- **No mass import of current Discord members.** That would need an explicit member-to-Discord mapping and your permission.
- **No server-wide destructive actions.** Setup does not delete, rename or move existing channels/roles, ban members, or alter someone's role without `/roster_assign` with a selected Discord member.
- **Sheet credentials are powerful.** Use a dedicated Google service account. Start with Viewer. Grant Editor only when the write functions are needed.
- **Discord privacy:** the company treasury channel is Command-only; only **completed** contracts are posted publicly by default. `/contracts include_pending:true` is an ephemeral command-only reply.
- **A/ and regular GP personnel do not get radio callsigns.** Five permanent section “Actual” callsigns remain tied to lead billets, and Stratt retains the Hammer A/ role without one.
- **Unit tests** exercise the important payout, authorization-slot, injection and reputation stacking rules. They do **not** replace live Discord and Google API testing. This bot was not authenticated to Discord or deployed by ChatGPT.

### Developer checks

```bash
python -m compileall -q bot.py fps_sheets.py fps_logic.py fps_content.py
python -m unittest discover -s tests -v
```

Official documentation:
- Discord developers: https://discord.com/developers/docs/intro
- discord.py slash command examples: https://github.com/Rapptz/discord.py/tree/master/examples/app_commands
- gspread service-account guide: https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account

**Forgepoint Security — Forged into Soldiers.**