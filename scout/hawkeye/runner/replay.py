"""Replay Hawkeye review sessions.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scout.hawkeye.config import HawkeyeConfig
from scout.hawkeye.findings.schema import findings_hash
from scout.hawkeye.runner.playbook import run_review
from scout.hawkeye.trace.store import TraceStore


@dataclass
class ReplayReport:
    session_id: str
    dry_run: bool
    steps: list[dict]
    original_findings_hash: str | None
    replay_findings_hash: str | None
    match: bool | None


def _session_meta(trace: TraceStore) -> dict:
    for record in trace.iter_records():
        if record.get("type") == "session_start":
            return record
    return {}


def _original_findings_hash(trace: TraceStore) -> str | None:
    for record in reversed(trace.iter_records()):
        if record.get("type") == "session_end":
            return str(record.get("findings_hash") or "") or None
    return None


def replay_session(
    cfg: HawkeyeConfig,
    session_id: str,
    *,
    repo_root: Path,
    dry_run: bool = False,
) -> ReplayReport:
    trace = TraceStore.load(cfg.trace_dir, session_id)
    steps = trace.steps()
    original = _original_findings_hash(trace)
    if dry_run:
        return ReplayReport(
            session_id=session_id,
            dry_run=True,
            steps=steps,
            original_findings_hash=original,
            replay_findings_hash=None,
            match=None,
        )

    meta = _session_meta(trace)
    diff_ref = str(meta.get("diff_ref") or "HEAD~1")
    space = str(meta.get("space") or cfg.default_space)
    result = run_review(cfg, diff_ref=diff_ref, repo_root=repo_root, space=space)
    replay_hash = result.findings_hash
    return ReplayReport(
        session_id=session_id,
        dry_run=False,
        steps=steps,
        original_findings_hash=original,
        replay_findings_hash=replay_hash,
        match=(original == replay_hash) if original else None,
    )


def print_replay_report(report: ReplayReport) -> str:
    lines = [f"session: {report.session_id}", f"steps: {len(report.steps)}"]
    for step in report.steps:
        lines.append(
            f"  [{step.get('seq')}] {step.get('action')} "
            + json.dumps({k: v for k, v in step.items() if k not in {'type', 'seq', 'action', 'session_id', 'timestamp'}}, sort_keys=True)
        )
    if report.dry_run:
        lines.append(f"original findings_hash: {report.original_findings_hash}")
        return "\n".join(lines)
    lines.append(f"original findings_hash: {report.original_findings_hash}")
    lines.append(f"replay findings_hash:   {report.replay_findings_hash}")
    lines.append(f"match: {report.match}")
    return "\n".join(lines)
