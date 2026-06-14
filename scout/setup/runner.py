"""Setup wizard orchestration.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import httpx
import typer
from rich.console import Console

from scout.config import (
    EmbedConfig,
    SpaceEntry,
    bootstrap_scout_dir,
    load_config,
    load_secrets,
    prescan_path,
    register_space,
    save_config,
)
from scout.indexing import run_reindex
from scout.prescan.runner import (
    check_byte_cap,
    check_capacity,
    display_prescan_table,
    run_prescan,
    write_prescan_json,
)
from scout.setup.api_url import (
    build_scout_api_url,
    ensure_api_port_available,
    normalize_api_base_url,
    parse_api_base_url,
)
from scout.setup.embed import configure_embed
from scout.setup.prompts import (
    prompt_agent,
    prompt_api_base_url,
    prompt_setup_branch,
    prompt_skill_scope,
    set_console_callbacks,
)
from scout.setup.workspace import clone_git_workspace, resolve_local_root
from scout.skill.install import install_skill


async def run_setup(
    space: str,
    *,
    agent_override: str | None = None,
    force: bool = False,
    embed_batch_size: int = 0,
    reprobe_embed_batch: bool = False,
    console: Console | None = None,
) -> None:
    """Execute unified 4-branch setup wizard."""
    rich_console = console or Console()
    set_console_callbacks(
        print_fn=rich_console.print,
        print_red_fn=lambda msg: rich_console.print(f"[red]{msg}[/red]"),
        print_yellow_fn=lambda msg: rich_console.print(f"[yellow]{msg}[/yellow]"),
    )

    home = bootstrap_scout_dir()
    config = load_config(home)
    secrets = load_secrets(home)

    api_url = prompt_api_base_url(config)
    config.api_base_url = normalize_api_base_url(api_url)
    endpoint = parse_api_base_url(config.api_base_url)
    config.api_port = endpoint.port
    ensure_api_port_available(config)
    save_config(home, config)

    branch = prompt_setup_branch()

    if branch.uses_git:
        root_path = clone_git_workspace(force=force)
    else:
        root_path = resolve_local_root()

    embed_result = await configure_embed(branch, home, secrets, config, rich_console)

    entry = SpaceEntry(name=space, root=str(root_path))
    register_space(home, entry, config)
    config.embed = EmbedConfig(
        provider=embed_result.provider_name,
        model=embed_result.model,
        endpoint=embed_result.endpoint,
        dimensions=embed_result.dimensions,
    )
    save_config(home, config)

    prescan = run_prescan(root_path, entry.skip_globs, entry.skip_paths)
    display_prescan_table(rich_console, prescan)
    check_byte_cap(prescan, force=force)
    check_capacity(prescan)
    write_prescan_json(prescan_path(home, space), prescan)
    if not typer.confirm("Proceed with indexing?", default=True):
        raise SystemExit(0)

    try:
        version = await run_reindex(
            home,
            space,
            config,
            embed_result.provider,
            embed_batch_size=embed_batch_size,
            reprobe_embed_batch=reprobe_embed_batch,
            console=rich_console,
        )
    except Exception as exc:
        rich_console.print(f"[red]setup failed: {exc}[/red]")
        raise SystemExit(1) from exc
    rich_console.print(f"[green]Indexed space '{space}' (version {version})[/green]")

    await _probe_api_health(build_scout_api_url(config), rich_console)

    agent = prompt_agent(agent_override)
    global_install, project_install = prompt_skill_scope()
    scout_api = build_scout_api_url(config)
    try:
        paths = install_skill(
            agent,
            global_install=global_install,
            project_install=project_install,
            project_root=root_path,
            scout_api=scout_api,
            default_space=space,
            force=force,
        )
        for path in paths:
            rich_console.print(f"[green]Skill installed: {path}[/green]")
    except FileExistsError as exc:
        rich_console.print(f"[yellow]{exc}[/yellow]")


async def _probe_api_health(api_url: str, console: Console) -> None:
    """Warn if Scout API not reachable (serve may not be running yet)."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{api_url}/health")
            if resp.status_code != 200:
                console.print(
                    "[yellow]Scout API not healthy yet — run `scout serve`[/yellow]"
                )
    except httpx.HTTPError:
        console.print(
            "[yellow]Scout API unreachable — run `scout serve` when ready[/yellow]"
        )
