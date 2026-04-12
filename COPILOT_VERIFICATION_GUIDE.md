# Copilot Verification Guide

This file is for local VS Code + Copilot verification.

## What Copilot can verify automatically

Copilot can reliably verify:

1. Python syntax across the codebase
2. Importability of the main bot/cog/service/view modules
3. Local unit tests in `tests/`
4. Bot startup logs if a valid `.env` is present

Copilot cannot fully verify without a live Discord server:

1. Slash command visibility in Discord
2. Button/select/modal UX
3. DM validation flows
4. Heist live narration in channels
5. Real Groq responses

## What you need in VS Code

### Required

- Open the workspace folder: `C:\\Users\\arivm\\OneDrive\\Desktop\\vice-city-os`
- Python interpreter set to:
  - `C:\\Users\\arivm\\OneDrive\\Desktop\\vice-city-os\\.venv312\\Scripts\\python.exe`
- A real `.env` file with:
  - `DISCORD_TOKEN`
  - `GUILD_ID`
  - `MAYOR_ROLE_NAME`
  - `DATABASE_PATH`
  - `TIMEZONE`
  - `LOG_LEVEL`

### Strongly recommended

- If you are setting this up on a fresh machine, keep the workspace in a normal local folder instead of a OneDrive-synced path.
- SQLite can behave badly in synced folders on Windows, especially for fresh database creation and journal files.
- If you must stay in OneDrive, point `DATABASE_PATH` at a normal local writable path outside OneDrive.

### Optional but recommended

- `GROQ_API_KEY` for AI scene testing
- A dedicated Discord test server
- A second and third Discord account for co-op testing

## VS Code tasks to run

Use these tasks in order:

1. `Verify: Syntax`
2. `Verify: Imports`
3. `Verify: Unit Tests`
4. `Run: Vice City Bot`

## Suggested Copilot Chat prompt

Use this in Copilot Chat:

```text
Verify this Discord bot workspace without changing code unless a real defect is found.

Do this in order:
1. Run the VS Code task "Verify: Syntax"
2. Run the VS Code task "Verify: Imports"
3. Run the VS Code task "Verify: Unit Tests"
4. If .env contains a real DISCORD_TOKEN and GUILD_ID, run "Run: Vice City Bot" and inspect startup logs
5. Summarize:
   - what passed
   - what failed
   - what still requires manual Discord-side testing

Important:
- Distinguish code problems from environment/setup problems
- Do not claim Discord UI flows were verified unless the bot actually ran and was tested in Discord
- Treat Pillow native load failures as environment restrictions unless a code error points elsewhere
```

## Manual Discord checklist after Copilot passes

Run these in Discord:

1. `/join`
2. `/profile`
3. `/shop`
4. `/operate`
5. Trigger a bust and test negotiation modal
6. `/wanted`
7. `/heist plan casino`
8. `/help`

## Expected results

- No raw tracebacks should appear in Discord
- All major responses should be embeds
- Slash and prefix commands should both exist
- Failed drug runs should offer negotiation
- Heat 5 should create a wanted flow
- Heists should produce live-style updates and a recap
- Unit tests should pass without needing a temporary on-disk SQLite file
