"""Trace mining — cluster findings and suggest rule candidates.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Pagination and batch_size for large trace dirs.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from scout.hawkeye.trace.store import TraceStore


def _pattern_key(finding: dict[str, Any]) -> str:
    scout = finding.get("scout") or {}
    return "|".join(
        [
            str(finding.get("rule_id") or ""),
            str(scout.get("identification_method") or ""),
            str((scout.get("graph_evidence") or {}).get("edge") or ""),
        ]
    )


def mine_traces(
    trace_dir: Path,
    *,
    threshold: int = 3,
    limit: int | None = None,
    offset: int = 0,
    batch_size: int | None = None,
) -> dict[str, Any]:
    clusters: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "sessions": [], "example": None}
    )
    paths = sorted(trace_dir.glob("*.jsonl"))
    if offset:
        paths = paths[offset:]
    if limit is not None:
        paths = paths[:limit]

    processed = 0
    for path in paths:
        session_id = path.stem
        store = TraceStore.load(trace_dir, session_id)
        for record in store.iter_records():
            if record.get("type") != "finding":
                continue
            finding = record.get("finding") or {}
            key = _pattern_key(finding)
            cluster = clusters[key]
            cluster["count"] += 1
            cluster["sessions"].append(session_id)
            if cluster["example"] is None:
                cluster["example"] = finding
            processed += 1
            if batch_size is not None and processed >= batch_size:
                break
        if batch_size is not None and processed >= batch_size:
            break

    candidates: list[dict[str, Any]] = []
    for idx, (key, data) in enumerate(sorted(clusters.items(), key=lambda kv: -kv[1]["count"])):
        if data["count"] < threshold:
            continue
        example = data["example"] or {}
        candidates.append(
            {
                "candidate_id": f"CAND-{idx+1:03d}",
                "pattern_key": key,
                "occurrences": data["count"],
                "sessions": sorted(set(data["sessions"]))[:10],
                "status": "pending",
                "suggested_rule": {
                    "id": f"HKY-MINED-{idx+1:03d}",
                    "name": f"Mined pattern {key[:40]}",
                    "type": "path_glob",
                    "enabled": False,
                    "severity": example.get("severity") or "warning",
                    "path_glob": (example.get("scout") or {}).get("rel_path") or "**",
                    "message": example.get("message") or "Mined review pattern",
                },
            }
        )
    return {
        "candidates": candidates,
        "threshold": threshold,
        "offset": offset,
        "limit": limit,
        "batch_size": batch_size,
    }


def write_candidates(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(report, handle, sort_keys=False)
