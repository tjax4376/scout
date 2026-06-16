"""Backend selection for Hawkeye review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from scout.hawkeye.backends.base import ReviewBackend
from scout.hawkeye.backends.filesystem import FilesystemReviewBackend
from scout.hawkeye.backends.graph import GraphReviewBackend, graph_backend
from scout.hawkeye.config import HawkeyeConfig
from scout.hawkeye.discovery import discover_scout_for_setup, fetch_scout_spaces
from scout.hawkeye.trace.store import TraceStore
from scout.setup.api_url import probe_scout_health

BackendMode = Literal["auto", "graph", "filesystem"]
ResolvedBackend = Literal["graph", "filesystem"]

GRAPH_ONLY_RULE_TYPES = frozenset({"graph_neighbor", "staleness_gate"})


def filter_rules_for_backend(
    rules: list[dict],
    backend_name: ResolvedBackend,
) -> tuple[list[dict], list[str]]:
    """Return rules to evaluate and ids skipped (filesystem graph-only rules)."""
    if backend_name != "filesystem":
        return rules, []
    skipped: list[str] = []
    kept: list[dict] = []
    for rule in rules:
        if rule.get("enabled", True) is False:
            kept.append(rule)
            continue
        if str(rule.get("type") or "") in GRAPH_ONLY_RULE_TYPES:
            skipped.append(str(rule.get("id") or ""))
        else:
            kept.append(rule)
    if skipped:
        print(
            f"hawkeye: filesystem backend skipped graph-only rules: {', '.join(skipped)}",
            file=sys.stderr,
        )
    return kept, [sid for sid in skipped if sid]


def _scout_available(cfg: HawkeyeConfig, repo_root: Path, project: bool) -> tuple[str, str] | None:
    override = cfg.scout_api.strip().rstrip("/") if cfg.scout_api else None
    api_url = discover_scout_for_setup(
        repo_root,
        project=project,
        scout_api_override=override,
    )
    if not api_url and override and probe_scout_health(override):
        api_url = override
    if not api_url:
        return None
    try:
        spaces = fetch_scout_spaces(api_url)
    except ValueError:
        return None
    space = cfg.default_space if cfg.default_space in spaces else (spaces[0] if spaces else None)
    if not space:
        return None
    return api_url, space


def resolve_backend(
    mode: BackendMode,
    *,
    cfg: HawkeyeConfig,
    repo_root: Path,
    session_id: str,
    trace: TraceStore,
    project: bool = False,
) -> tuple[ReviewBackend, ResolvedBackend, str]:
    """Select backend; returns (backend, resolved_mode, space_name)."""
    if mode == "filesystem":
        return (
            FilesystemReviewBackend(repo_root=repo_root, trace=trace),
            "filesystem",
            cfg.default_space or "local",
        )

    scout = _scout_available(cfg, repo_root, project)
    if mode == "graph":
        if not scout:
            raise RuntimeError(
                "graph backend requires Scout API — start `scout serve` or use --backend filesystem"
            )
        api_url, space = scout
        return (
            graph_backend(
                scout_api=api_url,
                space=space,
                session_id=session_id,
                trace=trace,
                repo_root=repo_root,
            ),
            "graph",
            space,
        )

    # auto
    if scout:
        api_url, space = scout
        return (
            graph_backend(
                scout_api=api_url,
                space=space,
                session_id=session_id,
                trace=trace,
                repo_root=repo_root,
            ),
            "graph",
            space,
        )
    print("hawkeye: Scout not found — using filesystem backend", file=sys.stderr)
    return (
        FilesystemReviewBackend(repo_root=repo_root, trace=trace),
        "filesystem",
        cfg.default_space or "local",
    )
