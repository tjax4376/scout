"""Agent skill install for Cursor, Pi, OpenCode.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import shutil
from pathlib import Path

AGENT_PATHS = {
    "cursor": [
        {
            "name": "search_scout",
            "template": "search_scout",
            "global": Path.home() / ".cursor" / "skills" / "search_scout",
            "project": lambda root: root / ".cursor" / "skills" / "search_scout",
        },
        {
            "name": "add_memory",
            "template": "add_memory",
            "global": Path.home() / ".cursor" / "skills" / "add_memory",
            "project": lambda root: root / ".cursor" / "skills" / "add_memory",
        },
        {
            "name": "ask_scout",
            "template": "ask_scout",
            "global": Path.home() / ".cursor" / "skills" / "ask_scout",
            "project": lambda root: root / ".cursor" / "skills" / "ask_scout",
        },
    ],
    "pi": [
        {
            "name": "search-scout",
            "template": "search_scout",
            "global": Path.home() / ".pi" / "skills" / "search-scout",
            "project": lambda root: root / ".pi" / "skills" / "search-scout",
        },
        {
            "name": "add-memory",
            "template": "add_memory",
            "global": Path.home() / ".pi" / "skills" / "add-memory",
            "project": lambda root: root / ".pi" / "skills" / "add-memory",
        },
        {
            "name": "ask-scout",
            "template": "ask_scout",
            "global": Path.home() / ".pi" / "skills" / "ask-scout",
            "project": lambda root: root / ".pi" / "skills" / "ask-scout",
        },
    ],
    "opencode": [
        {
            "name": "search_scout",
            "template": "search_scout",
            "global": Path.home() / ".config" / "opencode" / "skills" / "search_scout",
            "project": lambda root: root / ".opencode" / "skills" / "search_scout",
        },
        {
            "name": "add_memory",
            "template": "add_memory",
            "global": Path.home() / ".config" / "opencode" / "skills" / "add_memory",
            "project": lambda root: root / ".opencode" / "skills" / "add_memory",
        },
        {
            "name": "ask_scout",
            "template": "ask_scout",
            "global": Path.home() / ".config" / "opencode" / "skills" / "ask_scout",
            "project": lambda root: root / ".opencode" / "skills" / "ask_scout",
        },
    ],
}


def skill_template_path(skill_name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / skill_name


def _skill_template_for_config(skill_config: dict) -> Path:
    """Resolve the template directory for a skill config entry."""
    return skill_template_path(skill_config["template"])


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

    installed: list[Path] = []

    for skill_config in AGENT_PATHS[agent]:
        skill_name = skill_config["name"]
        template = _skill_template_for_config(skill_config)
        if not template.exists():
            raise FileNotFoundError(f"skill template missing: {template}")

        targets: list[Path] = []
        if global_install:
            targets.append(skill_config["global"])
        if project_install:
            targets.append(skill_config["project"](project_root))

        for dest in targets:
            if dest.exists() and not force:
                raise FileExistsError(
                    f"skill {skill_name} exists at {dest}; use --force to overwrite"
                )
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
