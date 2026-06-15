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
import uvicorn
from rich.console import Console
from rich.json import JSON

from scout.api.app import create_app
from scout.cli.errors import cli_fail, format_and_exit
from scout import __version__
from scout.config import (
    bootstrap_scout_dir,
    get_embed_api_key,
    graph_bin_path,
    index_db_path,
    load_config,
    load_secrets,
    manifest_path,
    pid_path,
    scout_home,
    validate_embed,
    validate_space,
)
from scout.embed.registry import build_provider
from scout.graph_find import graph_path_search
from scout.indexing import INDEX_MODE, run_reindex
from scout.prescan.runner import check_byte_cap, check_capacity, run_prescan
from scout.setup.api_url import build_scout_api_url, parse_api_base_url
from scout.setup.runner import run_setup
from scout.serve.lifecycle import stop_serve

console = Console()


def _home() -> Path:
    from scout.config import scout_home

    return scout_home()


def _resolve_home() -> Path | None:
    try:
        return scout_home()
    except Exception:
        return None


def _require_core() -> None:
    if scout_core is None:
        cli_fail("scout_core not built. Run: maturin develop")


def _print_version() -> None:
    console.print(f"scout {__version__}")
    console.print(f"  package: {Path(__file__).resolve().parent.parent}")
    console.print(f"  executable: {Path(sys.executable).resolve()}")
    console.print(f"  index mode: {INDEX_MODE}")


def _usage() -> None:
    console.print(
        "Usage:\n"
        "  scout <space> setup [--agent cursor|pi|opencode] [--force]\n"
        "  scout <space> reindex [--force]\n"
        "  scout <space> search <query> [--top-k N]  # vector or graph path match\n"
        "  scout serve [--embed] [--no-warm-cache]\n"
        "  scout stop-serve\n"
        "  scout version\n"
        "\n"
        "Examples:\n"
        "  scout myapp setup --agent cursor\n"
        "  scout myapp search \"auth handler\"\n"
        "  scout serve --embed\n"
        "  scout stop-serve"
    )


def _parse_flags(
    argv: list[str],
) -> tuple[list[str], bool, str | None, int, int, bool]:
    force = False
    agent: str | None = None
    top_k = 10
    embed_batch = 0  # 0 = auto-probe
    reprobe_embed_batch = False
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--force":
            force = True
        elif arg == "--reprobe-embed-batch":
            reprobe_embed_batch = True
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
    return cleaned, force, agent, top_k, embed_batch, reprobe_embed_batch


def _validate_embed_batch(embed_batch: int) -> None:
    if embed_batch < 0:
        cli_fail("--embed-batch must be 0 (auto) or a positive integer")


def _main_impl(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        _usage()
        sys.exit(0)

    if args[0] in {"version", "--version", "-V"}:
        _print_version()
        return

    if args[0] == "serve":
        serve_args = args[1:]
        embed_mode = "--embed" in serve_args
        warm_cache = "--no-warm-cache" not in serve_args
        home = bootstrap_scout_dir()
        config = load_config(home)
        api_url = build_scout_api_url(config)
        endpoint = parse_api_base_url(api_url)
        pid_file = pid_path(home)
        if pid_file.exists():
            existing = pid_file.read_text(encoding="utf-8").strip()
            cli_fail(f"scout serve already running (pid {existing})")
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        try:
            mode_label = " (embed)" if embed_mode else ""
            console.print(f"[green]Serving{mode_label} on {api_url}[/green]")
            graph_url = api_url.removesuffix("/v1") + "/graph"
            console.print(f"[green]Graph UI: {graph_url}[/green]")
            uvicorn.run(
                create_app(embed_mode=embed_mode, warm_cache=warm_cache),
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
            cli_fail(result.message)
        else:
            console.print(f"[yellow]{result.message}[/yellow]")
        return

    positional, force, agent, top_k, embed_batch, reprobe_embed_batch = _parse_flags(args)
    if len(positional) < 2:
        _usage()
        sys.exit(1)

    space = positional[0]
    cmd = positional[1]
    _require_core()

    if cmd == "setup":
        asyncio.run(
            run_setup(
                space,
                agent_override=agent,
                force=force,
                console=console,
            )
        )
    elif cmd == "reindex":
        home = _home()
        config = load_config(home)
        entry = validate_space(home, space)
        prescan = run_prescan(
            Path(entry.root),
            entry.skip_globs,
            entry.skip_paths,
            respect_gitignore=entry.respect_gitignore,
        )
        check_byte_cap(prescan, force=force)
        check_capacity(prescan)
        version = asyncio.run(
            run_reindex(home, space, config, console=console)
        )
        console.print(f"[green]Reindex complete: {version}[/green]")
    elif cmd == "search":
        if len(positional) < 3:
            cli_fail("missing query")
        query = " ".join(positional[2:])
        home = _home()
        config = load_config(home)
        entry = validate_space(home, space)
        if scout_core.py_index_exists(str(index_db_path(home, space))):
            embed = validate_embed(config)
            secrets = load_secrets(home)
            stale, index_version = scout_core.py_check_staleness(
                entry.root,
                str(manifest_path(home, space)),
                embed.provider or "",
                embed.model or "",
                embed.dimensions or 0,
                entry.skip_globs,
                entry.skip_paths,
                entry.respect_gitignore,
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
            try:
                payload = graph_path_search(
                    home, space, config, query, top_k=top_k
                )
            except ValueError as exc:
                cli_fail(str(exc))
            if not payload["hits"]:
                console.print(
                    "[yellow]No graph matches — try a path fragment or symbol name[/yellow]"
                )
            console.print(JSON(json.dumps(payload)))
            if payload.get("stale"):
                console.print("[yellow]Index is stale — run reindex[/yellow]")
    else:
        _usage()
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    try:
        _main_impl(argv)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        format_and_exit(exc, _resolve_home())


if __name__ == "__main__":
    main()
