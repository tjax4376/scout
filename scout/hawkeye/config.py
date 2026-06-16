"""Hawkeye configuration loading and merge.

Metadata: v1.3.0 | Scout Contributors | 2026-06-15
Change rationale: PyInstaller frozen pack path, filesystem defaults without config.yaml.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml import YAMLError

GLOBAL_HAWKEYE_DIR = Path.home() / ".hawkeye"
PACK_V1_DIR = Path(__file__).resolve().parent / "rules" / "pack_v1"

REQUIRED_RULE_FIELDS = {"id", "type", "severity"}
REQUIRED_ANTIPATTERN_FIELDS = {"id", "type", "severity"}

ALLOWED_RULE_TYPES = frozenset(
    {
        "graph_neighbor",
        "symbol_diff_overlap",
        "text_hunk",
        "staleness_gate",
        "anti_pattern_ref",
        "path_glob",
    }
)


@dataclass
class HawkeyeConfig:
    """Resolved Hawkeye configuration for a review run."""

    scout_api: str
    default_space: str
    config_dir: Path
    trace_dir: Path
    rules: list[dict[str, Any]] = field(default_factory=list)
    antipatterns: list[dict[str, Any]] = field(default_factory=list)


def user_config_dir(project_root: Path | None = None) -> Path:
    if project_root is not None:
        project_cfg = project_root / ".hawkeye"
        if project_cfg.is_dir():
            return project_cfg
    return GLOBAL_HAWKEYE_DIR


def load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping in {path}")
    return data


def validate_rules(rules: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each rule must be a mapping")
        missing = REQUIRED_RULE_FIELDS - set(rule)
        if missing:
            raise ValueError(f"rule missing fields {sorted(missing)}: {rule.get('id')}")
        rid = str(rule["id"])
        if rid in seen:
            raise ValueError(f"duplicate rule id: {rid}")
        seen.add(rid)
        rtype = str(rule["type"])
        if rtype not in ALLOWED_RULE_TYPES:
            raise ValueError(f"rule {rid} has invalid type {rtype!r}; allowed: {sorted(ALLOWED_RULE_TYPES)}")
        if rule.get("enabled", True) is False:
            continue
        if rtype == "anti_pattern_ref" and not rule.get("anti_pattern_id"):
            raise ValueError(f"rule {rid} type anti_pattern_ref requires anti_pattern_id")


def validate_antipatterns(items: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each antipattern must be a mapping")
        missing = REQUIRED_ANTIPATTERN_FIELDS - set(item)
        if missing:
            raise ValueError(f"antipattern missing fields {sorted(missing)}: {item.get('id')}")
        aid = str(item["id"])
        if aid in seen:
            raise ValueError(f"duplicate antipattern id: {aid}")
        seen.add(aid)


def merge_by_id(base: list[dict[str, Any]], overlay: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {str(item["id"]): dict(item) for item in base}
    for item in overlay:
        item_id = str(item["id"])
        if item_id in merged:
            print(
                f"hawkeye config: rule id {item_id!r} replaced by overlay",
                file=sys.stderr,
            )
            updated = dict(merged[item_id])
            updated.update(dict(item))
            merged[item_id] = updated
        else:
            merged[item_id] = dict(item)
    return [dict(item) for item in merged.values()]


def _frozen_pack_dir() -> Path | None:
    """PyInstaller one-file extracts datas under sys._MEIPASS."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    for rel in (
        Path("scout") / "hawkeye" / "rules" / "pack_v1",
        Path("hawkeye") / "rules" / "pack_v1",
    ):
        candidate = Path(meipass) / rel
        if candidate.is_dir():
            return candidate
    return None


def _read_pack_yaml(name: str) -> dict[str, Any]:
    frozen = _frozen_pack_dir()
    if frozen is not None:
        path = frozen / name
        if path.is_file():
            return load_yaml_file(path)
    try:
        from importlib.resources import files

        ref = files("scout.hawkeye.rules.pack_v1").joinpath(name)
        text = ref.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError(f"expected mapping in packaged {name}")
        return data
    except (ModuleNotFoundError, TypeError, FileNotFoundError, YAMLError, ValueError):
        path = PACK_V1_DIR / name
        try:
            return load_yaml_file(path)
        except FileNotFoundError as exc:
            raise ValueError(f"Failed to load default rule pack ({name}): {exc}") from exc
        except ValueError as exc:
            raise ValueError(f"Failed to load default rule pack ({name}): {exc}") from exc


def _load_pack_yaml(name: str) -> dict[str, Any]:
    return _read_pack_yaml(name)


def load_rules_from_paths(*paths: Path | None) -> list[dict[str, Any]]:
    pack = _load_pack_yaml("rules.yaml")
    rules = [dict(item) for item in list(pack.get("rules") or [])]
    for path in paths:
        if path is None or not path.exists():
            continue
        data = load_yaml_file(path)
        rules = merge_by_id(rules, list(data.get("rules") or []))
    validate_rules(rules)
    return rules


def load_antipatterns_from_paths(*paths: Path | None) -> list[dict[str, Any]]:
    pack = _load_pack_yaml("antipatterns.yaml")
    items = [dict(item) for item in list(pack.get("antipatterns") or [])]
    for path in paths:
        if path is None or not path.exists():
            continue
        data = load_yaml_file(path)
        items = merge_by_id(items, list(data.get("antipatterns") or []))
    validate_antipatterns(items)
    return items


def load_config_or_defaults(
    project_root: Path | None = None,
    *,
    rules_file: Path | None = None,
    antipatterns_file: Path | None = None,
) -> HawkeyeConfig:
    """Load config.yaml when present; else embedded pack + cwd `.hawkeye/traces`."""
    cfg_dir = user_config_dir(project_root)
    if (cfg_dir / "config.yaml").is_file():
        return load_config(project_root, rules_file=rules_file, antipatterns_file=antipatterns_file)

    root = project_root or Path.cwd()
    local_dir = root / ".hawkeye"
    trace_dir = local_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    rules_paths: list[Path | None] = [
        local_dir / "rules.yaml" if (local_dir / "rules.yaml").is_file() else None,
        rules_file,
    ]
    antipaths: list[Path | None] = [
        local_dir / "antipatterns.yaml" if (local_dir / "antipatterns.yaml").is_file() else None,
        antipatterns_file,
    ]
    return HawkeyeConfig(
        scout_api="",
        default_space="local",
        config_dir=local_dir,
        trace_dir=trace_dir,
        rules=load_rules_from_paths(*rules_paths),
        antipatterns=load_antipatterns_from_paths(*antipaths),
    )


def load_config(
    project_root: Path | None = None,
    *,
    rules_file: Path | None = None,
    antipatterns_file: Path | None = None,
) -> HawkeyeConfig:
    cfg_dir = user_config_dir(project_root)
    main_cfg_path = cfg_dir / "config.yaml"
    if not main_cfg_path.exists():
        raise FileNotFoundError(
            f"Hawkeye not configured at {cfg_dir}; run: python -m scout.hawkeye setup"
        )
    main = load_yaml_file(main_cfg_path)
    if "scout_api" not in main:
        raise ValueError(f"{main_cfg_path}: missing required field scout_api")
    if "default_space" not in main:
        raise ValueError(f"{main_cfg_path}: missing required field default_space")
    rules_paths = [cfg_dir / "rules.yaml", rules_file]
    antipaths = [cfg_dir / "antipatterns.yaml", antipatterns_file]
    trace_dir = Path(str(main.get("trace_dir") or (cfg_dir / "traces")))
    return HawkeyeConfig(
        scout_api=str(main["scout_api"]).rstrip("/"),
        default_space=str(main["default_space"]),
        config_dir=cfg_dir,
        trace_dir=trace_dir,
        rules=load_rules_from_paths(*rules_paths),
        antipatterns=load_antipatterns_from_paths(*antipaths),
    )
