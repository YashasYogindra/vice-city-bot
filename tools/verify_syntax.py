from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "vicecity"
    errors: list[tuple[Path, Exception]] = []
    for path in root.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except Exception as exc:  # pragma: no cover - verification script
            errors.append((path, exc))

    if errors:
        for path, exc in errors:
            print(f"ERROR {path}: {exc}")
        return 1

    print("syntax-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
