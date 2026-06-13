"""Indexing orchestration — ties Rust core + embed providers.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import json
from pathlib import Path

import scout_core

from scout.config import (
    ScoutConfig,
    graph_bin_path,
    index_db_path,
    manifest_path,
    validate_embed,
    validate_space,
)
from scout.embed.registry import EmbedProvider


async def run_reindex(
    home: Path,
    space: str,
    config: ScoutConfig,
    provider: EmbedProvider,
) -> str:
    """Full synchronous rebuild. Raises on failure; no partial index."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    if not scout_core.py_acquire_reindex_lock(space):
        raise RuntimeError("reindex in progress")

    try:
        entry = validate_space(home, space)
        embed = validate_embed(config)
        root = Path(entry.root)

        files = scout_core.py_scan_workspace(
            str(root),
            skip_globs=entry.skip_globs,
            skip_paths=entry.skip_paths,
        )
        files_json = json.dumps(
            [
                {
                    "rel_path": f.rel_path,
                    "size": f.size,
                    "mtime_secs": f.mtime_secs,
                    "language": f.language,
                    "is_binary": False,
                }
                for f in files
            ]
        )

        index_version = f"{embed.provider}:{embed.model}:{embed.dimensions}"
        build_data = json.loads(build_json)
        snapshot, chunks = build_data[0], build_data[1]

        texts = [c["text"] for c in chunks]
        embeddings = await provider.embed(embed.model, texts)
        embeddings_json = json.dumps(embeddings)

        db_tmp = index_db_path(home, space).with_suffix(".db.tmp")
        graph_tmp = graph_bin_path(home, space).with_suffix(".bin.tmp")

        scout_core.py_write_index(
            str(db_tmp),
            embed.model,
            embed.dimensions,
            json.dumps(chunks),
            embeddings_json,
        )
        scout_core.py_save_graph(str(graph_tmp), json.dumps(snapshot))

        # Atomic swap
        db_final = index_db_path(home, space)
        graph_final = graph_bin_path(home, space)
        db_final.parent.mkdir(parents=True, exist_ok=True)
        graph_final.parent.mkdir(parents=True, exist_ok=True)
        if db_final.exists():
            db_final.unlink()
        if graph_final.exists():
            graph_final.unlink()
        db_tmp.rename(db_final)
        graph_tmp.rename(graph_final)

        version = scout_core.py_write_manifest(
            str(manifest_path(home, space)),
            files_json,
            embed.provider,
            embed.model,
            embed.dimensions,
        )
        return version
    finally:
        scout_core.py_release_reindex_lock()
