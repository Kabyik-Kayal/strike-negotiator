"""Strike Negotiator backend package.

Loads repo-level .env values on import so local development commands can
consume environment settings without requiring shell export steps.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if value and value[0] in {'"', "'"}:
            value = _strip_wrapping_quotes(value)
        elif " #" in value:
            # Keep simple inline comments out of unquoted values.
            value = value.split(" #", 1)[0].rstrip()

        os.environ.setdefault(key, value)


_load_dotenv(ROOT_DIR / ".env")

