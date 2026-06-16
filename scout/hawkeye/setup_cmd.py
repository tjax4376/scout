"""Hawkeye setup — initialize config, rules, and anti-patterns.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: URL validation, atomic config write, mode 0o600.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from scout.hawkeye.config import PACK_V1_DIR, load_yaml_file
from scout.hawkeye.io_utils import atomic_write_text


def _validate_scout_api_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid scout_api URL: {url!r} (require http/https with host)")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            "hawkeye setup: warning — http:// is allowed for localhost; prefer https elsewhere",
            file=sys.stderr,
        )
    return url.rstrip("/")


def run_setup(
    *,
    scout_api: str,
    space: str,
    project: bool = False,
    project_root: Path | None = None,
    rules_file: Path | None = None,
    antipatterns_file: Path | None = None,
    force: bool = False,
) -> Path:
    import scout.hawkeye.config as hawkeye_config

    scout_api = _validate_scout_api_url(scout_api)
    target = (project_root / ".hawkeye") if project else hawkeye_config.GLOBAL_HAWKEYE_DIR
    if target.exists() and not force:
        raise FileExistsError(f"Hawkeye config exists at {target}; use --force to overwrite")

    target.mkdir(parents=True, exist_ok=True)
    traces = target / "traces"
    traces.mkdir(parents=True, exist_ok=True)

    config = {
        "scout_api": scout_api,
        "default_space": space,
        "trace_dir": str(traces),
    }
    atomic_write_text(
        target / "config.yaml",
        yaml.safe_dump(config, sort_keys=False),
        mode=0o600,
    )

    rules_dest = target / "rules.yaml"
    antipatterns_dest = target / "antipatterns.yaml"
    src_rules = rules_file or (PACK_V1_DIR / "rules.yaml")
    src_antipatterns = antipatterns_file or (PACK_V1_DIR / "antipatterns.yaml")
    shutil.copy2(src_rules, rules_dest)
    shutil.copy2(src_antipatterns, antipatterns_dest)

    load_yaml_file(rules_dest)
    load_yaml_file(antipatterns_dest)
    return target
