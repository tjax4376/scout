"""Indexing orchestration — graph-only rebuild via Rust core.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
Change: graph-only indexing; no sqlite chunks or embed pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import scout_core
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from scout.config import (
    ScoutConfig,
    graph_bin_path,
    index_db_path,
    manifest_path,
    space_scan_kwargs,
    validate_space,
)

INDEX_MODE = "graph-only"
DEFAULT_EMBED_BATCH = 10


async def embed_texts_batched(
    provider,
    model: str,
    texts: list[str],
    *,
    batch_size: int = DEFAULT_EMBED_BATCH,
    console: Console | None = None,
) -> list[list[float]]:
    """Embed texts in batches (retained for embed batch probe tests / future embed-index)."""
    if not texts:
        return []

    out: list[list[float]] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )
    with progress:
        task = progress.add_task("Embedding chunks", total=len(texts))
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = await provider.embed(model, batch)
            out.extend(vecs)
            progress.advance(task, len(batch))
    return out


async def run_reindex(
    home: Path,
    space: str,
    config: ScoutConfig,
    *,
    console: Console | None = None,
) -> str:
    """Full synchronous graph rebuild. Raises on failure; no partial index."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    ui = console or Console()

    if not scout_core.py_acquire_reindex_lock(space):
        raise RuntimeError("reindex in progress")

    try:
        entry = validate_space(home, space)
        root = Path(entry.root)

        ui.print("[cyan]Scanning workspace...[/cyan]")
        files = scout_core.py_scan_workspace(str(root), **space_scan_kwargs(entry))
        ui.print(f"  {len(files)} files")
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

        ui.print("[cyan]Building graph...[/cyan]")
        index_version = "graph-only:v1"
        snapshot_json = scout_core.py_build_graph(
            space, str(root), files_json, index_version
        )
        snapshot = json.loads(snapshot_json)
        ui.print(f"  {len(snapshot.get('nodes', []))} graph nodes")

        ui.print("[cyan]Writing graph cache...[/cyan]")
        graph_tmp = graph_bin_path(home, space).with_suffix(".bin.tmp")
        scout_core.py_save_graph(str(graph_tmp), snapshot_json)

        ui.print("[cyan]Finalizing index (atomic swap)...[/cyan]")
        graph_final = graph_bin_path(home, space)
        graph_final.parent.mkdir(parents=True, exist_ok=True)
        if graph_final.exists():
            graph_final.unlink()
        graph_tmp.rename(graph_final)

        db_final = index_db_path(home, space)
        if db_final.exists():
            db_final.unlink()

        version = scout_core.py_write_graph_manifest(
            str(manifest_path(home, space)),
            files_json,
        )
        ui.print(f"[green]Index complete[/green] (version {version})")
        return version
    finally:
        scout_core.py_release_reindex_lock()
