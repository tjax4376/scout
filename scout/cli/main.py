"""Scout CLI — setup, reindex, search, serve.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import scout_core
import typer
import uvicorn
from rich.console import Console
from rich.json import JSON

from scout.api.app import create_app
from scout.config import (
    EmbedConfig,
    ScoutConfig,
    SpaceEntry,
    bootstrap_scout_dir,
    graph_bin_path,
    index_db_path,
    load_config,
    load_secrets,
    manifest_path,
    pid_path,
    prescan_path,
    register_space,
    save_config,
    save_secrets,
    scout_home,
    validate_embed,
    validate_space,
)
from scout.embed.registry import (
    DEFAULT_PORTS,
    LOCAL_PROVIDER_WARNING,
    build_provider,
    filter_embed_models,
    find_free_api_port,
    is_local_provider,
    scan_local_endpoint,
)
from scout.indexing import run_reindex
from scout.prescan.runner import (
    check_byte_cap,
    check_capacity,
    display_prescan_table,
    run_prescan,
    write_prescan_json,
)
from scout.skill.install import install_skill

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _home() -> Path:
    return scout_home()


def _require_core() -> None:
    if scout_core is None:
        console.print("[red]scout_core not built. Run: maturin develop[/red]")
        raise typer.Exit(1)


@app.command("setup")
def setup_cmd(
    space: str = typer.Argument(..., help="Space name"),
    agent: Optional[str] = typer.Option(None, "--agent", help="cursor|pi|opencode"),
    force: bool = typer.Option(False, "--force", help="Bypass byte cap / overwrite skill"),
) -> None:
    """Interactive setup: root → provider → model → prescan → index → skill."""
    _require_core()
    asyncio.run(_setup_async(space, agent, force))


async def _setup_async(space: str, agent: str | None, force: bool) -> None:
    home = bootstrap_scout_dir()
    config = load_config(home)

    root = typer.prompt("Workspace root path", default=str(Path.cwd()))
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        console.print(f"[red]invalid root: {root_path}[/red]")
        raise typer.Exit(1)

    provider_name = typer.prompt(
        "Embed provider",
        default="lmstudio",
        show_default=True,
    )
    if provider_name not in {"openrouter", "lmstudio", "omlx", "unsloth-studio"}:
        console.print("[red]invalid provider[/red]")
        raise typer.Exit(1)

    secrets = load_secrets(home)
    endpoint = ""
    if provider_name == "openrouter":
        api_key = secrets.get("openrouter_api_key") or typer.prompt(
            "OpenRouter API key", hide_input=True
        )
        secrets["openrouter_api_key"] = api_key
        save_secrets(home, secrets)
        provider = build_provider("openrouter", api_key=api_key)
    else:
        if is_local_provider(provider_name):
            console.print(f"[yellow]{LOCAL_PROVIDER_WARNING}[/yellow]")
        default_port = DEFAULT_PORTS.get(provider_name, 1234)
        start = int(typer.prompt("Port range start", default=str(default_port)))
        end = int(typer.prompt("Port range end", default=str(start + 6)))
        found = await scan_local_endpoint("127.0.0.1", start, end)
        if not found:
            manual = typer.prompt("Manual endpoint URL (or empty to abort)", default="")
            if not manual:
                console.print("[red]no endpoint found[/red]")
                raise typer.Exit(1)
            found = manual.rstrip("/")
            if not found.endswith("/v1"):
                found = f"{found}/v1"
        endpoint = found
        provider = build_provider(provider_name, endpoint=endpoint)

    models = await provider.list_models()
    embed_models = await filter_embed_models(provider, models)
    if not embed_models:
        console.print("[red]no embed-capable models found[/red]")
        raise typer.Exit(1)
    console.print("Models:")
    for i, m in enumerate(embed_models[:20]):
        console.print(f"  [{i}] {m}")
    idx = int(typer.prompt("Select model index", default="0"))
    model = embed_models[idx]
    dims = await provider.probe_dimensions(model)

    entry = SpaceEntry(name=space, root=str(root_path))
    register_space(home, entry, config)
    config.embed = EmbedConfig(
        provider=provider_name,
        model=model,
        endpoint=endpoint,
        dimensions=dims,
    )
    if config.api_port < 8741:
        config.api_port = find_free_api_port()
    save_config(home, config)

    prescan = run_prescan(root_path, entry.skip_globs, entry.skip_paths)
    display_prescan_table(console, prescan)
    check_byte_cap(prescan, force=force)
    check_capacity(prescan)
    write_prescan_json(prescan_path(home, space), prescan)
    if not typer.confirm("Proceed with indexing?", default=True):
        raise typer.Exit(0)

    try:
        version = await run_reindex(home, space, config, provider)
    except Exception as exc:
        console.print(f"[red]setup failed: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Indexed space '{space}' (version {version})[/green]")

    if agent:
        scope = typer.prompt("Install skill: global / project / both", default="both")
        g = scope in {"global", "both"}
        p = scope in {"project", "both"}
        api = f"http://127.0.0.1:{config.api_port}/v1"
        try:
            paths = install_skill(
                agent,
                global_install=g,
                project_install=p,
                project_root=root_path,
                scout_api=api,
                default_space=space,
                force=force,
            )
            for path in paths:
                console.print(f"[green]Skill installed: {path}[/green]")
        except FileExistsError as exc:
            console.print(f"[yellow]{exc}[/yellow]")


@app.command("reindex")
def reindex_cmd(
    space: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Sync full rebuild for a space."""
    _require_core()
    home = _home()
    config = load_config(home)
    embed = validate_embed(config)
    secrets = load_secrets(home)
    provider = build_provider(
        embed.provider,
        api_key=secrets.get("openrouter_api_key"),
        endpoint=embed.endpoint or None,
    )
    entry = validate_space(home, space)
    prescan = run_prescan(Path(entry.root), entry.skip_globs, entry.skip_paths)
    check_byte_cap(prescan, force=force)
    check_capacity(prescan)
    version = asyncio.run(run_reindex(home, space, config, provider))
    console.print(f"[green]Reindex complete: {version}[/green]")


@app.command("search")
def search_cmd(
    space: str = typer.Argument(...),
    query: str = typer.Argument(...),
    top_k: int = typer.Option(10, "--top-k"),
) -> None:
    """Vector search via pyo3 (no HTTP)."""
    _require_core()
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
        api_key=secrets.get("openrouter_api_key"),
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


@app.command("serve")
def serve_cmd() -> None:
    """Start foreground API server with PID lock."""
    home = bootstrap_scout_dir()
    config = load_config(home)
    pid_file = pid_path(home)
    if pid_file.exists():
        existing = pid_file.read_text(encoding="utf-8").strip()
        console.print(f"[red]scout serve already running (pid {existing})[/red]")
        raise typer.Exit(1)

    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    try:
        console.print(f"[green]Serving on http://127.0.0.1:{config.api_port}[/green]")
        uvicorn.run(
            create_app(),
            host="127.0.0.1",
            port=config.api_port,
            log_level="info",
        )
    finally:
        if pid_file.exists():
            pid_file.unlink()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
