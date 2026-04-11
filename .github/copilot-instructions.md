# Vice City OS Copilot Instructions

This repository is a single-server Discord bot for a cinematic crime simulation.

## Architecture

- Entry point: `main.py`
- Bot wiring: `vicecity/bot.py`
- Command surface: `vicecity/cogs/`
- Game logic: `vicecity/services/`
- Persistence: `vicecity/repositories/`
- UI interactions: `vicecity/views/`
- Models: `vicecity/models/`
- Tests: `tests/`

## Runtime assumptions

- Python interpreter: `${workspaceFolder}\\.venv312\\Scripts\\python.exe`
- Environment file: `${workspaceFolder}\\.env`
- This bot is intentionally single-guild focused for demo reliability.
- Slash and prefix commands should both work.

## What to verify first

When asked to verify changes, prefer this order:

1. Run `Verify: Syntax`
2. Run `Verify: Imports`
3. Run `Verify: Unit Tests`
4. If `.env` contains a real token and guild ID, run `Run: Vice City Bot`
5. For Discord behavior, report what still requires manual in-server testing

## Important product behavior

- Keep all economy math deterministic.
- Gemini is only used for:
  - bust negotiation scenes
  - heist narration / recap flavor
- If Gemini is unavailable, deterministic fallback copy must be used.
- Visual generation must never crash the bot. If Pillow is blocked, degrade gracefully.
- All user-facing replies should remain embed-first.

## Known environment caveats

- `pytest` is not part of the current setup; prefer `unittest`.
- Some machines may block Pillow native DLL loading. Treat that as an environment issue, not automatically a code defect.
- Discord UI, DM validation, and slash-command sync cannot be fully verified without a live token and server.

## If verification fails

- Distinguish between:
  - code issues
  - missing environment setup
  - machine policy restrictions
- Never claim live Discord flows are verified unless the bot was actually run against Discord.
