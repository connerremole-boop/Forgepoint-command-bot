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
| Reputation | `/reputation` displays 0–100 score, tier and **draft** penalties |
| Publish/update | `/publish channel:company-roster` edits the previous bot-authored post; similarly for other info channels |
| Contract writes* | `/contract_add`, `/contract_result` fill only non-formula input cells |
| Purchase writes* | `/purchase` validates Catalog ID, quantity and available CR; preserves formula cells |
| Roster writes* | `/roster_assign`, `/roster_unassign` enforce authorized slot limits and preserve fixed leadership callsigns |
| Reputation writes** | `/reputation_event` adds approved events while preserving sheet formulas; checks duplicate/buyout stacking |

\* Disabled until `ENABLE_SHEETS_WRITES=true`. \** Additionally disabled until `ENABLE_REPUTATION_WRITES=true` because the reputation system is still a **proposal**.

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

The reputation system begins at a **proposed** 50/100 with proposed mission bonuses/penalties, including **−25 for an enemy buyout that betrays an existing client**. Keep `ENABLE_REPUTATION_WRITES=false` until Rex/Kahuna approve the reputation point values. Then switch it to `true` and restart. The `/reputation_event` choices mirror your live Reputation Meter scoring table.

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