"""Indexing orchestration — ties Rust core + embed providers.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
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
    save_config,
    validate_embed,
    validate_space,
)
from scout.embed.batch_probe import resolve_embed_batch_size
from scout.embed.registry import EmbedProvider

DEFAULT_EMBED_BATCH = 4096  # fallback when auto-probe unavailable


async def embed_texts_batched(
    provider: EmbedProvider,
    model: str,
    texts: list[str],
    *,
    batch_size: int = DEFAULT_EMBED_BATCH,
    console: Console | None = None,
) -> list[list[float]]:
    """Embed texts in batches with progress bar."""
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
    provider: EmbedProvider,
    *,
    embed_batch_size: int = 0,
    reprobe_embed_batch: bool = False,
    console: Console | None = None,
) -> str:
    """Full synchronous rebuild. Raises on failure; no partial index."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")

    ui = console or Console()

    if not scout_core.py_acquire_reindex_lock(space):
        raise RuntimeError("reindex in progress")

    try:
        entry = validate_space(home, space)
        embed = validate_embed(config)
        root = Path(entry.root)

        ui.print("[cyan]Scanning workspace...[/cyan]")
        files = scout_core.py_scan_workspace(
            str(root),
            skip_globs=entry.skip_globs,
            skip_paths=entry.skip_paths,
        )
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

        ui.print("[cyan]Building graph and chunks...[/cyan]")
        index_version = f"{embed.provider}:{embed.model}:{embed.dimensions}"
        build_json = scout_core.py_build_index(space, str(root), files_json, index_version)
        build_data = json.loads(build_json)
        snapshot, chunks = build_data[0], build_data[1]
        ui.print(f"  {len(snapshot.get('nodes', []))} graph nodes, {len(chunks)} chunks")

        texts = [c["text"] for c in chunks]

        if embed_batch_size > 0:
            batch = embed_batch_size
        else:
            ui.print("[cyan]Resolving embed batch from provider /models...[/cyan]")
            batch = await resolve_embed_batch_size(
                provider,
                embed.model,
                embed.dimensions,
                texts,
                cli_override=0,
                cached=embed.embed_batch_size,
                reprobe=reprobe_embed_batch,
            )
            if embed.embed_batch_size != batch:
                config.embed.embed_batch_size = batch
                save_config(home, config)
            ui.print(f"  embed batch: {batch}")

        embeddings = await embed_texts_batched(
            provider,
            embed.model,
            texts,
            batch_size=batch,
            console=ui,
        )
        embeddings_json = json.dumps(embeddings)

        ui.print("[cyan]Writing vector index...[/cyan]")
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

        ui.print("[cyan]Finalizing index (atomic swap)...[/cyan]")
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
        ui.print(f"[green]Index complete[/green] (version {version})")
        return version
    finally:
        scout_core.py_release_reindex_lock()
