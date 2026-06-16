"""Deterministic Hawkeye review playbook orchestrator.

Metadata: v1.3.0 | Scout Contributors | 2026-06-15
Change rationale: ReviewBackend injection for graph vs filesystem modes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scout.hawkeye.backends.resolve import BackendMode, filter_rules_for_backend, resolve_backend
from scout.hawkeye.config import HawkeyeConfig
from scout.hawkeye.findings.schema import Finding, findings_hash
from scout.hawkeye.rules.engine import ReviewContext, evaluate_rules
from scout.hawkeye.runner.diff_scope import DiffScope, git_diff_scope, map_changed_symbols
from scout.hawkeye.runner.path_scope import PathScope, directory_scope
from scout.hawkeye.trace.store import TraceStore

ReviewScope = DiffScope | PathScope


@dataclass
class ReviewResult:
    session_id: str
    findings: list[Finding]
    findings_hash: str
    scope: ReviewScope
    trace_path: Path
    stale: bool
    backend: str


def _session_ref(scope: ReviewScope, diff_ref: str) -> str:
    if isinstance(scope, PathScope):
        return scope.scope_ref
    return diff_ref


def run_review(
    cfg: HawkeyeConfig,
    *,
    diff_ref: str = "HEAD~1",
    scope: ReviewScope | None = None,
    repo_root: Path,
    space: str | None = None,
    session_id: str | None = None,
    backend_mode: BackendMode = "auto",
    project: bool = False,
) -> ReviewResult:
    sid = session_id or str(uuid.uuid4())
    trace = TraceStore(cfg.trace_dir, sid)
    backend, resolved_mode, space_name = resolve_backend(
        backend_mode,
        cfg=cfg,
        repo_root=repo_root,
        session_id=sid,
        trace=trace,
        project=project,
    )
    if space:
        space_name = space

    if scope is None and resolved_mode == "filesystem":
        scope = directory_scope(repo_root, Path("."))
    elif scope is None:
        scope = git_diff_scope(repo_root, diff_ref)

    rules, skipped = filter_rules_for_backend(cfg.rules, resolved_mode)
    trace.start_session(
        space=space_name,
        diff_ref=_session_ref(scope, diff_ref),
        changed_paths=scope.changed_paths,
        backend=resolved_mode,
        skipped_rules=skipped,
    )

    symbols_by_prefix: dict[str, list[dict[str, Any]]] = {}
    all_symbols: list[dict[str, Any]] = []
    for prefix in scope.path_prefixes or [""]:
        syms = backend.list_symbols(prefix)
        symbols_by_prefix[prefix] = syms
        seen = {str(s.get("node_id")) for s in all_symbols}
        for sym in syms:
            nid = str(sym.get("node_id") or "")
            if nid and nid not in seen:
                all_symbols.append(sym)
                seen.add(nid)

    changed_symbols = map_changed_symbols(all_symbols, scope.changed_lines)
    neighbors_by_node: dict[str, list[dict[str, Any]]] = {}
    neighbors_logged: set[str] = set()
    file_text: dict[str, str] = {}

    for sym in changed_symbols:
        node_id = str(sym.get("node_id") or "")
        if not node_id:
            continue
        neighbors = backend.neighbors(node_id, depth=2, max_nodes=50)
        neighbors_by_node[node_id] = neighbors
        neighbors_logged.add(node_id)

        rel = str(sym.get("rel_path") or "")
        start = int(sym.get("start_line") or 1)
        end = int(sym.get("end_line") or start)
        if rel and rel not in file_text:
            file_text[rel] = backend.read_file(rel, start_line=start, end_line=end)

    for rel in scope.changed_paths:
        if rel not in file_text:
            file_text[rel] = backend.read_file(rel)

    ctx = ReviewContext(
        session_id=sid,
        space=space_name,
        changed_lines=scope.changed_lines,
        symbols_by_prefix=symbols_by_prefix,
        changed_symbols=changed_symbols,
        neighbors_by_node=neighbors_by_node,
        file_text=file_text,
        neighbors_logged=neighbors_logged,
        stale=backend.stale,
    )
    findings = evaluate_rules(rules, cfg.antipatterns, ctx)
    fhash = findings_hash(findings)
    for finding in findings:
        trace.add_finding(finding.to_dict())
    trace.end_session(fhash)
    return ReviewResult(
        session_id=sid,
        findings=findings,
        findings_hash=fhash,
        scope=scope,
        trace_path=trace.path,
        stale=backend.stale,
        backend=resolved_mode,
    )
