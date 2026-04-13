from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MODULES = [
    "sinbot.bot",
    "sinbot.cogs.core",
    "sinbot.cogs.operations",
    "sinbot.cogs.heist",
    "sinbot.cogs.war",
    "sinbot.cogs.mayor",
    "sinbot.cogs.social",
    "sinbot.cogs.casino",
    "sinbot.cogs.auction",
    "sinbot.cogs.betting",
    "sinbot.cogs.fighting",
    "sinbot.services.city",
    "sinbot.services.operations",
    "sinbot.services.heist",
    "sinbot.services.heat",
    "sinbot.services.groq_service",
    "sinbot.services.visuals",
    "sinbot.services.casino",
    "sinbot.gifs",
    "sinbot.views.action_hub",
    "sinbot.views.negotiation",
]


def main() -> int:
    for module_name in MODULES:
        importlib.import_module(module_name)
    print("imports-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
