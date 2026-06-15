"""CLI error formatting — friendly messages, no tracebacks by default.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
Change rationale: graceful CLI errors (cli-graceful-errors)
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import NoReturn

import yaml

FAREWELL = "Thanks for using Scout."
SETUP_HINT = "Run: scout <space> setup"


def is_debug() -> bool:
    """True when SCOUT_DEBUG is set to a truthy value."""
    return os.environ.get("SCOUT_DEBUG", "").lower() in ("1", "true", "yes")


def cli_fail(message: str) -> NoReturn:
    """Print a user-facing error, farewell, and exit with code 1."""
    print(message, file=sys.stderr)
    _print_farewell()
    raise SystemExit(1)


def format_and_exit(exc: BaseException, home: Path | None = None) -> NoReturn:
    """Map an exception to friendly stderr output and exit."""
    if is_debug() and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
        traceback.print_exc()

    for line in _lines_for_exception(exc, home):
        print(line, file=sys.stderr)
    _print_farewell()
    raise SystemExit(1)


def _print_farewell() -> None:
    print("", file=sys.stderr)
    print(FAREWELL, file=sys.stderr)


def _lines_for_exception(exc: BaseException, home: Path | None) -> list[str]:
    if isinstance(exc, yaml.YAMLError):
        return [
            f"Could not read Scout config: {exc}",
            SETUP_HINT,
        ]

    if isinstance(exc, ValueError):
        return _lines_for_value_error(str(exc), home)

    return ["Something went wrong. Set SCOUT_DEBUG=1 for details."]


def _lines_for_value_error(msg: str, home: Path | None) -> list[str]:
    if msg.startswith("unknown space:"):
        name = msg.split(":", 1)[1].strip()
        lines = [f"Unknown space: {name}"]
        configured = _configured_space_names(home)
        if configured:
            lines.append(f"Configured spaces: {', '.join(configured)}")
        lines.append(SETUP_HINT)
        return lines

    if " has no root path configured" in msg:
        return [msg, SETUP_HINT]

    if msg.startswith("space root not found:"):
        return [msg, SETUP_HINT]

    embed_missing = (
        "embed provider not configured",
        "embed model not configured",
        "embed dimensions not configured",
    )
    if msg in embed_missing:
        return [msg.replace("embed ", "Embed ").capitalize() + ".", SETUP_HINT]

    if msg.startswith("unknown embed provider:"):
        return [msg, SETUP_HINT]

    # Preserve other ValueError text (setup wizard, api_url validation, etc.).
    return [msg]


def _configured_space_names(home: Path | None) -> list[str]:
    if home is None:
        return []
    try:
        from scout.config import load_config

        return sorted(load_config(home).spaces.keys())
    except Exception:
        return []
