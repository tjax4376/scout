"""Setup wizard prompts.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import typer

from scout.config import ScoutConfig, get_embed_api_key
from scout.setup.api_url import DEFAULT_API_BASE_URL, normalize_api_base_url


class SetupBranch(Enum):
    LOCAL_LOCAL = 1
    LOCAL_REMOTE = 2
    GIT_LOCAL = 3
    GIT_REMOTE = 4

    @property
    def uses_git(self) -> bool:
        return self in {SetupBranch.GIT_LOCAL, SetupBranch.GIT_REMOTE}

    @property
    def uses_openrouter(self) -> bool:
        return self in {SetupBranch.LOCAL_REMOTE, SetupBranch.GIT_REMOTE}


BRANCH_LABELS = {
    SetupBranch.LOCAL_LOCAL: "1) Local files + Local LLM (lmstudio/omlx/unsloth-studio)",
    SetupBranch.LOCAL_REMOTE: "2) Local files + Remote LLM (OpenRouter)",
    SetupBranch.GIT_LOCAL: "3) Git repo (clone to cwd) + Local LLM",
    SetupBranch.GIT_REMOTE: "4) Git repo (clone to cwd) + Remote LLM (OpenRouter)",
}


def prompt_api_base_url(config: ScoutConfig) -> str:
    """Prompt for full Scout API base URL."""
    default = config.api_base_url or DEFAULT_API_BASE_URL
    while True:
        raw = typer.prompt("Scout API base URL", default=default)
        try:
            url = normalize_api_base_url(raw)
            break
        except ValueError as exc:
            console_print_red(str(exc))
    endpoint_host = url.split("://", 1)[1].split(":")[0].split("/")[0]
    if endpoint_host not in {"127.0.0.1", "localhost"}:
        console_print_yellow(
            "Warning: non-loopback host exposes Scout API on the network."
        )
    return url


def prompt_setup_branch() -> SetupBranch:
    """Present 4-branch setup menu."""
    console_print("Setup branch:")
    for branch in SetupBranch:
        console_print(f"  {BRANCH_LABELS[branch]}")
    choice = typer.prompt("Select branch", default="1")
    try:
        idx = int(choice)
        return SetupBranch(idx)
    except (ValueError, KeyError):
        console_print_red("invalid branch selection")
        raise SystemExit(1)


def prompt_openrouter_api_key(secrets: dict[str, str], config: ScoutConfig) -> str:
    """Prompt OpenRouter key with leave-blank-to-keep."""
    existing = secrets.get("openrouter_api_key", "")
    stored_model = (
        config.embed.model if config.embed.provider == "openrouter" else None
    )
    if existing:
        hint = "OpenRouter API key on file"
        if stored_model:
            hint += f" for model {stored_model}"
        hint += " — leave blank to keep"
        entered = typer.prompt(hint, default="", hide_input=True)
        return entered or existing
    return typer.prompt("OpenRouter API key", hide_input=True)


def prompt_local_api_key(
    provider: str,
    secrets: dict[str, str],
    config: ScoutConfig,
) -> str:
    """Prompt local embed API key with leave-blank-to-keep."""
    existing = get_embed_api_key(secrets, provider) or ""
    stored_model = config.embed.model if config.embed.provider == provider else None
    if existing:
        hint = f"{provider} API key on file"
        if stored_model:
            hint += f" for model {stored_model}"
        hint += " — leave blank to keep"
        entered = typer.prompt(hint, default="", hide_input=True)
        return entered or existing
    return typer.prompt(
        "Embed API key (required if server uses auth; Enter to skip)",
        default="",
        hide_input=True,
    )


def prompt_local_provider() -> str:
    """Prompt for local embed provider name."""
    provider = typer.prompt(
        "Local embed provider",
        default="lmstudio",
    )
    if provider not in {"lmstudio", "omlx", "unsloth-studio"}:
        console_print_red("invalid local provider")
        raise SystemExit(1)
    return provider


def prompt_agent(agent_override: str | None) -> str:
    """Prompt agent selection or use override."""
    if agent_override:
        if agent_override not in {"cursor", "pi", "opencode"}:
            console_print_red("invalid agent")
            raise SystemExit(1)
        return agent_override
    agent = typer.prompt(
        "Target agent (cursor / pi / opencode)",
        default="cursor",
    )
    if agent not in {"cursor", "pi", "opencode"}:
        console_print_red("invalid agent")
        raise SystemExit(1)
    return agent


def prompt_skill_scope() -> tuple[bool, bool]:
    """Prompt global/project/both skill install scope."""
    scope = typer.prompt("Install skill: global / project / both", default="both")
    global_install = scope in {"global", "both"}
    project_install = scope in {"project", "both"}
    return global_install, project_install


@dataclass
class ConsoleCallbacks:
    """Injectable console for tests."""

    print_fn: Callable[[str], None] = print
    print_red_fn: Callable[[str], None] = print
    print_yellow_fn: Callable[[str], None] = print


_callbacks = ConsoleCallbacks()


def set_console_callbacks(
    *,
    print_fn: Callable[[str], None] | None = None,
    print_red_fn: Callable[[str], None] | None = None,
    print_yellow_fn: Callable[[str], None] | None = None,
) -> None:
    global _callbacks
    if print_fn:
        _callbacks.print_fn = print_fn
    if print_red_fn:
        _callbacks.print_red_fn = print_red_fn
    if print_yellow_fn:
        _callbacks.print_yellow_fn = print_yellow_fn


def console_print(msg: str) -> None:
    _callbacks.print_fn(msg)


def console_print_red(msg: str) -> None:
    _callbacks.print_red_fn(msg)


def console_print_yellow(msg: str) -> None:
    _callbacks.print_yellow_fn(msg)
