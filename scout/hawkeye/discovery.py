"""Scout API discovery for Hawkeye setup.

Metadata: v1.2.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import yaml

from scout.config import scout_home
from scout.setup.api_url import discover_scout_api_url, probe_scout_health


def _read_scout_api_from_config(config_path: Path) -> str | None:
    if not config_path.is_file():
        return None
    try:
        with config_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    api_url = str(data.get("api_base_url") or "").strip().rstrip("/")
    if not api_url:
        port = data.get("api_port")
        if port:
            api_url = f"http://127.0.0.1:{port}/v1"
    if not api_url:
        return None
    if not api_url.endswith("/v1"):
        api_url = f"{api_url}/v1"
    if probe_scout_health(api_url):
        return api_url
    return None


def discover_scout_for_setup(
    project_root: Path | None,
    *,
    project: bool = False,
    scout_api_override: str | None = None,
) -> str | None:
    """Resolve Scout API URL for Hawkeye setup."""
    if scout_api_override:
        url = scout_api_override.strip().rstrip("/")
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        if probe_scout_health(url):
            return url
        raise ValueError(f"Scout API not healthy at {url}")

    candidates: list[Path] = []
    if project and project_root is not None:
        candidates.append(project_root / ".scout" / "config.yaml")
    try:
        candidates.append(scout_home() / "config.yaml")
    except Exception:
        pass

    for path in candidates:
        found = _read_scout_api_from_config(path)
        if found:
            return found

    return discover_scout_api_url()


def fetch_scout_spaces(api_url: str) -> list[str]:
    """List space names from Scout GET /v1/spaces/list."""
    base = api_url.rstrip("/")
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{base}/spaces/list")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ValueError(f"failed to list Scout spaces at {base}: {exc}") from exc
    spaces_raw = data.get("spaces") if isinstance(data, dict) else None
    if not isinstance(spaces_raw, list):
        raise ValueError(f"unexpected spaces/list response from {base}")
    names: list[str] = []
    for item in spaces_raw:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def resolve_setup_space(
    spaces: list[str],
    space_flag: str | None,
    *,
    yes_flag: bool,
) -> str:
    """Pick Scout space for setup — flag, single space, or interactive prompt."""
    if space_flag:
        if space_flag not in spaces:
            available = ", ".join(spaces) if spaces else "(none)"
            raise ValueError(f"space {space_flag!r} not in Scout config; available: {available}")
        return space_flag
    if not spaces:
        raise ValueError("Scout returned no configured spaces")
    if len(spaces) == 1:
        return spaces[0]
    if yes_flag:
        raise ValueError(
            f"multiple Scout spaces found ({', '.join(spaces)}); use --space to choose"
        )
    print("Available Scout spaces:", file=sys.stderr)
    for idx, name in enumerate(spaces, start=1):
        print(f"  {idx}. {name}", file=sys.stderr)
    while True:
        try:
            choice = input("Select space number: ").strip()
            pick = int(choice)
            if 1 <= pick <= len(spaces):
                return spaces[pick - 1]
        except (ValueError, EOFError):
            pass
        print("Invalid selection — enter a number from the list.", file=sys.stderr)


def validate_space_exists(api_url: str, space: str, spaces: list[str]) -> None:
    """Confirm space appears in Scout spaces/list (authoritative for this API instance)."""
    if space not in spaces:
        available = ", ".join(spaces) if spaces else "(none)"
        raise ValueError(f"space {space!r} not in Scout config; available: {available}")


def prepare_setup(
    *,
    scout_api: str | None,
    space: str | None,
    project: bool,
    project_root: Path,
    yes: bool,
) -> tuple[str, str]:
    """Discover Scout URL and space; print proposal unless --yes."""
    if scout_api and space:
        api_url = discover_scout_for_setup(project_root, project=project, scout_api_override=scout_api)
        spaces = fetch_scout_spaces(api_url)
        chosen = resolve_setup_space(spaces, space, yes_flag=yes)
        validate_space_exists(api_url, chosen, spaces)
        return api_url, chosen

    api_url = discover_scout_for_setup(project_root, project=project, scout_api_override=scout_api)
    if not api_url:
        raise ValueError(
            "Scout API not found — start Scout with `scout serve` or pass --scout-api and --space"
        )

    spaces = fetch_scout_spaces(api_url)
    chosen = resolve_setup_space(spaces, space, yes_flag=yes)
    validate_space_exists(api_url, chosen, spaces)

    if not yes:
        print(f"Proposed Scout API: {api_url}", file=sys.stderr)
        print(f"Proposed space: {chosen}", file=sys.stderr)
        confirm = input("Continue with setup? [Y/n]: ").strip().lower()
        if confirm not in {"", "y", "yes"}:
            raise ValueError("setup cancelled")

    return api_url, chosen
