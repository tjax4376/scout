"""Scout CLI — setup, reindex, search, serve.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
Command shape: `scout <space> setup|reindex|search` and `scout serve`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import scout_core
import typer
import uvicorn
from rich.console import Console
from rich.json import JSON

from scout.api.app import create_app
from scout.config import (
    bootstrap_scout_dir,
    get_embed_api_key,
    graph_bin_path,
    index_db_path,
    load_config,
    load_secrets,
    manifest_path,
    pid_path,
    prescan_path,
    scout_home,
    validate_embed,
    validate_space,
)
from scout.embed.registry import build_provider
from scout.indexing import DEFAULT_EMBED_BATCH, run_reindex
from scout.prescan.runner import check_byte_cap, check_capacity, run_prescan
from scout.setup.api_url import build_scout_api_url, parse_api_base_url
from scout.setup.runner import run_setup
from scout.serve.lifecycle import stop_serve

console = Console()


def _home() -> Path:
    from scout.config import scout_home

    return scout_home()


def _require_core() -> None:
    if scout_core is None:
        console.print("[red]scout_core not built. Run: maturin develop[/red]")
        sys.exit(1)


def _usage() -> None:
    console.print(
        "Usage:\n"
        "  scout <space> setup [--agent cursor|pi|opencode] [--force] [--embed-batch N]\n"
        "  scout <space> reindex [--force] [--embed-batch N]\n"
        "  scout <space> search <query> [--top-k N]\n"
        "  scout serve\n"
        "  scout stop-serve\n"
        "\n"
        "Examples:\n"
        "  scout myapp setup --agent cursor\n"
        "  scout myapp search \"auth handler\"\n"
        "  scout stop-serve"
    )


def _parse_flags(
    argv: list[str],
) -> tuple[list[str], bool, str | None, int, int]:
    force = False
    agent: str | None = None
    top_k = 10
    embed_batch = DEFAULT_EMBED_BATCH
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--force":
            force = True
        elif arg == "--agent" and i + 1 < len(argv):
            i += 1
            agent = argv[i]
        elif arg == "--top-k" and i + 1 < len(argv):
            i += 1
            top_k = int(argv[i])
        elif arg == "--embed-batch" and i + 1 < len(argv):
            i += 1
            embed_batch = int(argv[i])
        else:
            cleaned.append(arg)
        i += 1
    return cleaned, force, agent, top_k, embed_batch


def _validate_embed_batch(embed_batch: int) -> None:
    if embed_batch < 1:
        console.print("[red]--embed-batch must be at least 1[/red]")
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        _usage()
        sys.exit(0)

    if args[0] == "serve":
        home = bootstrap_scout_dir()
        config = load_config(home)
        api_url = build_scout_api_url(config)
        endpoint = parse_api_base_url(api_url)
        pid_file = pid_path(home)
        if pid_file.exists():
            existing = pid_file.read_text(encoding="utf-8").strip()
            console.print(f"[red]scout serve already running (pid {existing})[/red]")
            sys.exit(1)
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        try:
            console.print(f"[green]Serving on {api_url}[/green]")
            uvicorn.run(
                create_app(),
                host=endpoint.host,
                port=endpoint.port,
                log_level="info",
            )
        finally:
            if pid_file.exists():
                pid_file.unlink()
        return

    if args[0] == "stop-serve":
        home = scout_home()
        result = stop_serve(home)
        if result.status == "stopped":
            console.print(f"[green]{result.message}[/green]")
        elif result.status == "failed":
            console.print(f"[red]{result.message}[/red]")
            sys.exit(1)
        else:
            console.print(f"[yellow]{result.message}[/yellow]")
        return

    positional, force, agent, top_k, embed_batch = _parse_flags(args)
    if len(positional) < 2:
        _usage()
        sys.exit(1)

    space = positional[0]
    cmd = positional[1]
    _require_core()

    if cmd == "setup":
        _validate_embed_batch(embed_batch)
        asyncio.run(
            run_setup(
                space,
                agent_override=agent,
                force=force,
                embed_batch_size=embed_batch,
                console=console,
            )
        )
    elif cmd == "reindex":
        _validate_embed_batch(embed_batch)
        home = _home()
        config = load_config(home)
        embed = validate_embed(config)
        secrets = load_secrets(home)
        provider = build_provider(
            embed.provider,
            api_key=get_embed_api_key(secrets, embed.provider),
            endpoint=embed.endpoint or None,
        )
        entry = validate_space(home, space)
        prescan = run_prescan(Path(entry.root), entry.skip_globs, entry.skip_paths)
        check_byte_cap(prescan, force=force)
        check_capacity(prescan)
        version = asyncio.run(
            run_reindex(
                home,
                space,
                config,
                provider,
                embed_batch_size=embed_batch,
                console=console,
            )
        )
        console.print(f"[green]Reindex complete: {version}[/green]")
    elif cmd == "search":
        if len(positional) < 3:
            console.print("[red]missing query[/red]")
            sys.exit(1)
        query = " ".join(positional[2:])
        home = _home()
        config = load_config(home)
        embed = validate_embed(config)
        entry = validate_space(home, space)
        secrets = load_secrets(home)
        stale, index_version = scout_core.py_check_staleness(
            entry.root,
            str(manifest_path(home, space)),
            embed.provider,
            embed.model,
            embed.dimensions,
            entry.skip_globs,
            entry.skip_paths,
        )
        provider = build_provider(
            embed.provider,
            api_key=get_embed_api_key(secrets, embed.provider),
            endpoint=embed.endpoint or None,
        )
        query_vec = asyncio.run(provider.embed(embed.model, [query]))[0]
        raw = scout_core.py_search(
            str(graph_bin_path(home, space)),
            str(index_db_path(home, space)),
            query_vec,
            top_k,
            0.0,
            None,
            None,
            stale,
            index_version,
        )
        console.print(JSON(raw))
        if stale:
            console.print("[yellow]Index is stale — run reindex[/yellow]")
    else:
        _usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
