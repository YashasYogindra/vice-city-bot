from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIFS_FILE = ROOT / "sinbot" / "gifs.py"


def load_gif_constants(path: Path) -> list[tuple[str, str]]:
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    constants: list[tuple[str, str]] = []
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not re.fullmatch(r"[A-Z_]+", target.id):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants.append((target.id, node.value.value))
    return constants


def check_url(url: str) -> tuple[int | None, str | None, str | None]:
    try:
        result = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                "8",
                "--connect-timeout",
                "5",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}|%{content_type}",
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or f"curl exit code {result.returncode}"
            return None, None, err
        body = (result.stdout or "").strip()
        status_text, _, content_type = body.partition("|")
        status = int(status_text) if status_text.isdigit() else None
        return status, content_type or None, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    constants = load_gif_constants(GIFS_FILE)
    failures: list[str] = []

    print(f"Checking {len(constants)} GIF constants in {GIFS_FILE}")
    for key, raw_url in constants:
        url = raw_url.strip()
        trim_issue = raw_url != url
        if not url:
            failures.append(f"{key}: empty URL")
            print(f"[FAIL] {key}: empty URL")
            continue

        status, content_type, error = check_url(url)
        is_image = bool(content_type and content_type.lower().startswith("image/"))
        looks_page = "tenor.com/" in url.lower() and not url.lower().endswith(('.gif', '.png', '.jpg', '.jpeg', '.webp'))

        issues: list[str] = []
        if trim_issue:
            issues.append("leading/trailing whitespace")
        if status != 200:
            issues.append(f"status={status!r}")
        if not is_image:
            issues.append(f"content-type={content_type!r}")
        if error:
            issues.append(error)
        if looks_page:
            issues.append("tenor page URL (not direct media URL)")

        if issues:
            failures.append(f"{key}: {', '.join(issues)}")
            print(f"[FAIL] {key}: {', '.join(issues)}")
        else:
            print(f"[OK]   {key}: {status} {content_type}")

    print("\nSummary")
    print(f"- Total: {len(constants)}")
    print(f"- Failures: {len(failures)}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
