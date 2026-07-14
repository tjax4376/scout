"""Graph-only structure ask — no embed, no LLM.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: ask-scout-structure — compose graph search + capped neighbor expand.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import scout_core

from scout.api.path_safety import PathSafetyError, rel_path_matches_prefix, validate_path_prefix
from scout.config import ScoutConfig, graph_bin_path
from scout.graph_find import graph_path_search

_LOG = logging.getLogger("scout.ask")

# Keys that would leak source into agent prompts — never return these.
_OMIT_HIT_KEYS = frozenset({"text", "compressed_text", "content", "body", "source"})


class AskGraphMissingError(Exception):
    """Raised when graph.bin is absent for a known space."""

    def __init__(self, message: str = "graph index not found; run scout <space> reindex") -> None:
        super().__init__(message)


def _compact_hit(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep structural fields only (no source / compressed text)."""
    return {
        "node_id": raw.get("node_id"),
        "kind": raw.get("kind"),
        "symbol": raw.get("symbol"),
        "rel_path": raw.get("rel_path") or "",
        "location_ref": raw.get("location_ref") or "",
        "start_line": raw.get("start_line") or 0,
        "end_line": raw.get("end_line") or 0,
        "score": float(raw.get("score") or 0.0),
    }


def _expand_neighbors(
    graph_path: Path,
    node_id: str,
    depth: int,
    remaining: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Expand neighbors for one seed; returns (extra_hits, edges, truncated_here)."""
    if remaining <= 0 or depth <= 0:
        return [], [], remaining <= 0

    try:
        raw = scout_core.py_expand_neighbors(str(graph_path), node_id, depth, remaining)
    except Exception as exc:
        _LOG.warning("neighbor expand failed for %s: %s", node_id, exc)
        return [], [], False

    payload = json.loads(raw)
    neighbors = payload.get("neighbors") or []
    extra: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    truncated = False

    for nbr in neighbors:
        if len(extra) >= remaining:
            truncated = True
            break
        nid = nbr.get("node_id")
        if not nid:
            continue
        extra.append(
            {
                "node_id": nid,
                "kind": nbr.get("kind"),
                "symbol": nbr.get("symbol"),
                "rel_path": nbr.get("rel_path") or "",
                "location_ref": nbr.get("location_ref") or "",
                "start_line": nbr.get("start_line") or 0,
                "end_line": nbr.get("end_line") or 0,
                "score": 0.0,
            }
        )
        edges.append(
            {
                "from_id": node_id,
                "to_id": nid,
                "kind": nbr.get("edge") or "",
            }
        )

    if len(neighbors) > remaining:
        truncated = True

    return extra, edges, truncated


def ask_structure(
    home: Path,
    space: str,
    config: ScoutConfig,
    query: str,
    *,
    top_k: int = 10,
    expand_depth: int = 1,
    max_nodes: int = 50,
    path_prefix: str | None = None,
) -> dict[str, Any]:
    """Answer a structure question from graph.bin only (no embed/LLM).

    Raises:
        ValueError: empty/invalid query or unsafe path_prefix
        AskGraphMissingError: missing graph index
        RuntimeError: scout_core unavailable
    """
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    needle = (query or "").strip()
    if not needle:
        raise ValueError("empty search query")
    if len(needle) > 5000:
        raise ValueError("query too long")

    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        raise AskGraphMissingError()

    try:
        safe_prefix = validate_path_prefix(path_prefix)
    except PathSafetyError as exc:
        raise ValueError(str(exc)) from exc

    top_k = max(1, min(int(top_k), 50))
    expand_depth = max(0, min(int(expand_depth), 2))
    max_nodes = max(1, min(int(max_nodes), 200))

    # Graph keyword/path match only — never touches embed registry or session index.
    search = graph_path_search(
        home,
        space,
        config,
        needle,
        top_k=top_k,
        dedupe_by_path=False,
    )

    raw_hits = [_compact_hit(h) for h in (search.get("hits") or [])]
    if safe_prefix:
        raw_hits = [
            h for h in raw_hits if rel_path_matches_prefix(str(h.get("rel_path") or ""), safe_prefix)
        ]

    # Cap seed hits by remaining node budget.
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    truncated = False

    for hit in raw_hits:
        nid = str(hit.get("node_id") or "")
        if not nid or nid in seen:
            continue
        if len(seen) >= max_nodes:
            truncated = True
            break
        seen.add(nid)
        hits.append(hit)

    edges: list[dict[str, Any]] = []
    if expand_depth > 0 and hits:
        for seed in list(hits):
            remaining = max_nodes - len(seen)
            if remaining <= 0:
                truncated = True
                break
            nid = str(seed.get("node_id") or "")
            if not nid:
                continue
            extra, new_edges, trunc_here = _expand_neighbors(
                graph_path, nid, expand_depth, remaining
            )
            if trunc_here:
                truncated = True
            for e in new_edges:
                edges.append(e)
            for node in extra:
                enid = str(node.get("node_id") or "")
                if not enid or enid in seen:
                    continue
                rel = str(node.get("rel_path") or "")
                if safe_prefix and rel and not rel_path_matches_prefix(rel, safe_prefix):
                    continue
                if len(seen) >= max_nodes:
                    truncated = True
                    break
                seen.add(enid)
                hits.append(node)

    # Final safety: strip forbidden keys if upstream ever adds them
    for hit in hits:
        for key in list(hit.keys()):
            if key in _OMIT_HIT_KEYS:
                del hit[key]

    return {
        "query": needle,
        "hits": hits,
        "edges": edges,
        "total": len(hits),
        "mode": "graph",
        "truncated": truncated,
        "stale": bool(search.get("stale")),
        "index_version": str(search.get("index_version") or ""),
    }
