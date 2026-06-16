"""Promote mined rule candidates after human approval.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Backup rules.yaml before overwrite on promote.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from scout.hawkeye.config import load_rules_from_paths, load_yaml_file, merge_by_id, validate_rules


def load_candidates(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"candidate rules not found: {path}")
    data = load_yaml_file(path)
    if "candidates" not in data:
        raise ValueError(f"invalid candidate file: {path}")
    return data


def promote_candidate(
    cfg_rules_path: Path,
    candidates_path: Path,
    candidate_id: str,
    *,
    approve: bool,
) -> None:
    data = load_candidates(candidates_path)
    candidates = list(data.get("candidates") or [])
    match = next((c for c in candidates if str(c.get("candidate_id")) == candidate_id), None)
    if match is None:
        raise ValueError(f"unknown candidate id: {candidate_id}")

    if approve:
        rule = dict(match.get("suggested_rule") or {})
        rule["enabled"] = True
        existing = load_yaml_file(cfg_rules_path)
        merged = merge_by_id(list(existing.get("rules") or []), [rule])
        validate_rules(merged)
        if cfg_rules_path.exists():
            shutil.copy2(cfg_rules_path, cfg_rules_path.with_suffix(".yaml.bak"))
        with cfg_rules_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump({"rules": merged}, handle, sort_keys=False)
        match["status"] = "promoted"
    else:
        match["status"] = "rejected"

    with candidates_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
