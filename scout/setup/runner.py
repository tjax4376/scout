"""Setup wizard orchestration.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
Updated: 2026-06-14 — graph-only indexing; no embed step.
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
    resolve_discovered_api_url,
)
from scout.setup.embed import configure_embed
from scout.setup.prompts import (
    prompt_agent,
    prompt_api_base_url,
    prompt_setup_branch,
    prompt_skill_scope,
    set_console_callbacks,
)
from scout.setup.workspace import (
    clone_git_workspace,
    prompt_index_subdirectory,
    resolve_local_root,
)
from scout.skill.install import install_skill


async def run_setup(
    space: str,
    *,
    agent_override: str | None = None,
    force: bool = False,
    console: Console | None = None,
) -> None:
    """Execute unified setup wizard (graph-only indexing)."""
    rich_console = console or Console()
    set_console_callbacks(
        print_fn=rich_console.print,
        print_red_fn=lambda msg: rich_console.print(f"[red]{msg}[/red]"),
        print_yellow_fn=lambda msg: rich_console.print(f"[yellow]{msg}[/yellow]"),
    )

    rich_console.print(
        "[dim]Graph-only indexing — builds graph.bin only; "
        "no full-repo embed. Session search: scout serve --embed[/dim]"
    )

    home = bootstrap_scout_dir()
    config = load_config(home)

    discovered = resolve_discovered_api_url(config)
    api_url = prompt_api_base_url(config, discovered=discovered)
    config.api_base_url = normalize_api_base_url(api_url)
    endpoint = parse_api_base_url(config.api_base_url)
    config.api_port = endpoint.port
    ensure_api_port_available(config)
    save_config(home, config)

    branch = prompt_setup_branch()

    if branch.uses_git:
        workspace_anchor = clone_git_workspace(force=force)
    else:
        workspace_anchor = resolve_local_root()

    index_root = prompt_index_subdirectory(workspace_anchor)
    entry = SpaceEntry(name=space, root=str(index_root))
    register_space(home, entry, config)
    save_config(home, config)

    prescan = run_prescan(
        index_root,
        entry.skip_globs,
        entry.skip_paths,
        respect_gitignore=entry.respect_gitignore,
    )
    display_prescan_table(rich_console, prescan)
    check_byte_cap(prescan, force=force)
    check_capacity(prescan)
    write_prescan_json(prescan_path(home, space), prescan)
    if not typer.confirm("Proceed with indexing?", default=True):
        raise SystemExit(0)

    try:
        version = await run_reindex(home, space, config, console=rich_console)
    except Exception as exc:
        rich_console.print(f"[red]setup failed: {exc}[/red]")
        raise SystemExit(1) from exc
    rich_console.print(f"[green]Indexed space '{space}' (version {version})[/green]")

    if typer.confirm(
        "Configure embed provider for scout serve --embed? (optional)",
        default=False,
    ):
        secrets = load_secrets(home)
        try:
            embed_result = await configure_embed(home, secrets, config, rich_console)
        except SystemExit:
            raise
        except Exception as exc:
            rich_console.print(f"[red]Embed setup failed: {exc}[/red]")
            rich_console.print(
                "[yellow]Embed not saved — edit config.yaml or re-run setup[/yellow]"
            )
        else:
            config.embed = EmbedConfig(
                provider=embed_result.provider_name,
                model=embed_result.model,
                endpoint=embed_result.endpoint,
                dimensions=embed_result.dimensions,
            )
            save_config(home, config)
            rich_console.print("[green]Embed provider saved for session search[/green]")

    await _probe_api_health(build_scout_api_url(config), rich_console)

    agent = prompt_agent(agent_override)
    global_install, project_install = prompt_skill_scope()
    scout_api = build_scout_api_url(config)
    try:
        paths = install_skill(
            agent,
            global_install=global_install,
            project_install=project_install,
            project_root=workspace_anchor,
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
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == "ok":
                    console.print(f"[green]Scout API reachable at {api_url}[/green]")
                    return
            console.print(
                "[yellow]Scout API not healthy yet — run `scout serve`[/yellow]"
            )
    except httpx.HTTPError:
        console.print(
            "[yellow]Scout API unreachable — run `scout serve` when ready[/yellow]"
        )
