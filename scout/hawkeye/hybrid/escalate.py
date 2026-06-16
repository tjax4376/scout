"""Hybrid escalation bundle for unmapped review hunks.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Atomic write and 5 MiB bundle size cap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scout.hawkeye.findings.schema import Finding
from scout.hawkeye.io_utils import atomic_write_text
from scout.hawkeye.runner.diff_scope import DiffScope
from scout.hawkeye.runner.path_scope import PathScope
from scout.hawkeye.trace.store import TraceStore

ReviewScope = DiffScope | PathScope

MAX_ESCALATION_BYTES = 5 * 1024 * 1024


def _line_ranges(lines: set[int]) -> list[dict[str, int]]:
    if not lines:
        return []
    ordered = sorted(lines)
    ranges: list[dict[str, int]] = []
    start = prev = ordered[0]
    for ln in ordered[1:]:
        if ln == prev + 1:
            prev = ln
            continue
        ranges.append({"start_line": start, "end_line": prev})
        start = prev = ln
    ranges.append({"start_line": start, "end_line": prev})
    return ranges


def unmapped_hunks(scope: ReviewScope, findings: list[Finding]) -> list[dict[str, Any]]:
    covered: dict[str, set[int]] = {}
    for f in findings:
        rel = f.rel_path
        covered.setdefault(rel, set())
        for ln in range(f.start_line, f.end_line + 1):
            covered[rel].add(ln)

    hunks: list[dict[str, Any]] = []
    for rel, changed in scope.changed_lines.items():
        uncovered = changed - covered.get(rel, set())
        if uncovered:
            hunks.append({"rel_path": rel, "line_ranges": _line_ranges(uncovered)})
    return hunks


def build_escalation_bundle(
    *,
    session_id: str,
    scope: ReviewScope,
    findings: list[Finding],
    trace: TraceStore,
) -> dict[str, Any]:
    mapped = [f for f in findings if f.mapped]
    unmapped = unmapped_hunks(scope, findings)
    steps = trace.steps()
    symbols_checked = sum(1 for s in steps if s.get("action") == "symbols")
    return {
        "session_id": session_id,
        "mapped_findings_count": len(mapped),
        "unmapped_hunks": unmapped,
        "trace_summary": {
            "steps": len(steps),
            "symbols_checked": symbols_checked,
            "neighbors_checked": sum(1 for s in steps if s.get("action") == "neighbors"),
            "file_reads": sum(1 for s in steps if s.get("action") == "file_read"),
        },
        "suggested_agent_prompt": (
            "Review unmapped hunks only. Trace context attached — symbols and neighbors "
            "already checked; do not repeat investigation steps."
        ),
    }


def _cap_bundle_size(bundle: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(bundle, indent=2)
    if len(payload.encode("utf-8")) <= MAX_ESCALATION_BYTES:
        return bundle
    capped = dict(bundle)
    hunks = list(capped.get("unmapped_hunks") or [])
    while hunks:
        hunks = hunks[:-1]
        capped["unmapped_hunks"] = hunks
        capped["_truncated"] = True
        if len(json.dumps(capped, indent=2).encode("utf-8")) <= MAX_ESCALATION_BYTES:
            print("hawkeye: escalation bundle truncated to size limit", file=sys.stderr)
            return capped
    capped["unmapped_hunks"] = []
    capped["_truncated"] = True
    print("hawkeye: escalation bundle truncated to size limit", file=sys.stderr)
    return capped


def write_escalation(path: Path, bundle: dict[str, Any]) -> None:
    capped = _cap_bundle_size(bundle)
    atomic_write_text(path, json.dumps(capped, indent=2) + "\n")
