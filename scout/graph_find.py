"""Graph path/symbol lookup for graph-only spaces (no vector index).

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import json
from pathlib import Path

import scout_core

from scout.config import ScoutConfig, graph_bin_path, manifest_path, validate_space


def graph_path_search(
    home: Path,
    space: str,
    config: ScoutConfig,
    query: str,
    *,
    top_k: int = 10,
) -> dict[str, object]:
    """Match indexed graph nodes by rel_path or symbol name (case-insensitive)."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    entry = validate_space(home, space)
    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        raise ValueError("graph index not found; run scout <space> reindex")

    raw = scout_core.py_list_symbols(str(graph_path), "", None)
    payload = json.loads(raw)
    needle = query.strip().lower()
    if not needle:
        raise ValueError("empty search query")

    scored: list[dict[str, object]] = []
    for sym in payload.get("symbols", []):
        rel = str(sym.get("rel_path") or "")
        symbol = str(sym.get("symbol") or "")
        rel_lower = rel.lower()
        symbol_lower = symbol.lower()

        if needle not in rel_lower and needle not in symbol_lower:
            continue

        score = _match_score(needle, rel_lower, symbol_lower)
        scored.append(
            {
                "node_id": sym.get("node_id"),
                "kind": sym.get("kind"),
                "symbol": sym.get("symbol"),
                "rel_path": rel,
                "location_ref": sym.get("location_ref"),
                "start_line": sym.get("start_line"),
                "end_line": sym.get("end_line"),
                "score": score,
            }
        )

    by_path: dict[str, dict[str, object]] = {}
    for hit in scored:
        rel = str(hit.get("rel_path") or "")
        if not rel:
            continue
        existing = by_path.get(rel)
        if existing is None or float(hit["score"]) > float(existing["score"]):
            by_path[rel] = hit

    hits = sorted(
        by_path.values(),
        key=lambda h: (-float(h["score"]), str(h.get("rel_path") or "")),
    )[: max(1, top_k)]

    stale, index_version = scout_core.py_check_staleness(
        entry.root,
        str(manifest_path(home, space)),
        config.embed.provider or "",
        config.embed.model or "",
        config.embed.dimensions or 0,
        entry.skip_globs,
        entry.skip_paths,
        entry.respect_gitignore,
    )

    return {
        "hits": hits,
        "graph_only": True,
        "stale": stale,
        "index_version": index_version,
    }


def _match_score(needle: str, rel_lower: str, symbol_lower: str) -> float:
    basename = rel_lower.rsplit("/", 1)[-1]
    if basename == needle:
        return 1.0
    if rel_lower.endswith("/" + needle) or rel_lower.endswith(needle):
        return 0.9
    if needle in rel_lower:
        return 0.7
    if needle in symbol_lower:
        return 0.5
    return 0.1
