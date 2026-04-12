from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MODULES = [
    "vicecity.bot",
    "vicecity.cogs.core",
    "vicecity.cogs.operations",
    "vicecity.cogs.heist",
    "vicecity.cogs.war",
    "vicecity.cogs.mayor",
    "vicecity.cogs.social",
    "vicecity.cogs.casino",
    "vicecity.services.city",
    "vicecity.services.operations",
    "vicecity.services.heist",
    "vicecity.services.heat",
    "vicecity.services.groq_service",
    "vicecity.services.visuals",
    "vicecity.services.casino",
    "vicecity.views.action_hub",
    "vicecity.views.negotiation",
]


def main() -> int:
    for module_name in MODULES:
        importlib.import_module(module_name)
    print("imports-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
