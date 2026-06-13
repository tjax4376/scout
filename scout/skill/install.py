"""Agent skill install for Cursor, Pi, OpenCode.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import shutil
from pathlib import Path

AGENT_PATHS = {
    "cursor": {
        "global": Path.home() / ".cursor" / "skills" / "search_scout",
        "project": lambda root: root / ".cursor" / "skills" / "search_scout",
    },
    "pi": {
        "global": Path.home() / ".pi" / "skills" / "search_scout",
        "project": lambda root: root / ".pi" / "skills" / "search_scout",
    },
    "opencode": {
        "global": Path.home() / ".config" / "opencode" / "skills" / "search_scout",
        "project": lambda root: root / ".opencode" / "skills" / "search_scout",
    },
}


def skill_template_path() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "search_scout"


def install_skill(
    agent: str,
    *,
    global_install: bool,
    project_install: bool,
    project_root: Path,
    scout_api: str,
    default_space: str,
    force: bool = False,
) -> list[Path]:
    if agent not in AGENT_PATHS:
        raise ValueError(f"unknown agent: {agent}")
    template = skill_template_path()
    if not template.exists():
        raise FileNotFoundError(f"skill template missing: {template}")

    installed: list[Path] = []
    targets: list[Path] = []
    if global_install:
        targets.append(AGENT_PATHS[agent]["global"])
    if project_install:
        targets.append(AGENT_PATHS[agent]["project"](project_root))

    for dest in targets:
        if dest.exists() and not force:
            raise FileExistsError(f"skill exists at {dest}; use --force to overwrite")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(template, dest)
        _inject_config(dest, scout_api, default_space)
        installed.append(dest)
    return installed


def _inject_config(dest: Path, scout_api: str, default_space: str) -> None:
    skill_md = dest / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    content = content.replace("{{SCOUT_API}}", scout_api)
    content = content.replace("{{DEFAULT_SPACE}}", default_space)
    skill_md.write_text(content, encoding="utf-8")
