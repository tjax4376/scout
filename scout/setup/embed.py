"""Embed provider setup flow.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
Updated: 2026-06-14 — drop SetupBranch.openrouter; prompt provider type directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import typer

from scout.config import ScoutConfig, embed_api_key_secret, save_secrets
from scout.embed.registry import (
    DEFAULT_PORTS,
    LOCAL_PROVIDER_WARNING,
    EmbedProvider,
    build_provider,
    filter_embed_models,
    is_local_provider,
    scan_local_endpoint,
)
from scout.setup.prompts import (
    console_print_red,
    console_print_yellow,
    prompt_local_api_key,
    prompt_local_provider,
    prompt_openrouter_api_key,
)


@dataclass
class EmbedSetupResult:
    provider_name: str
    model: str
    endpoint: str
    dimensions: int
    provider: EmbedProvider


def _prompt_provider_name(config: ScoutConfig) -> str:
    default = config.embed.provider or "lmstudio"
    if default == "openrouter":
        default_kind = "openrouter"
    else:
        default_kind = "local"
    kind = typer.prompt(
        "Embed provider type (local / openrouter)",
        default=default_kind,
    ).strip().lower()
    if kind == "openrouter":
        return "openrouter"
    if kind == "local":
        return prompt_local_provider()
    console_print_red("invalid provider type — use local or openrouter")
    raise SystemExit(1)


async def configure_embed(
    home,
    secrets: dict[str, str],
    config: ScoutConfig,
    console,
) -> EmbedSetupResult:
    """Run embed provider auth, model pick, and dimension probe."""
    provider_name = _prompt_provider_name(config)

    endpoint = ""
    if provider_name == "openrouter":
        api_key = prompt_openrouter_api_key(secrets, config)
        if not api_key:
            console_print_red("OpenRouter API key required")
            raise SystemExit(1)
        secrets["openrouter_api_key"] = api_key
        save_secrets(home, secrets)
        provider = build_provider("openrouter", api_key=api_key)
    else:
        if is_local_provider(provider_name):
            console_print_yellow(LOCAL_PROVIDER_WARNING)
        secret_key = embed_api_key_secret(provider_name)
        api_key = prompt_local_api_key(provider_name, secrets, config)
        if api_key:
            secrets[secret_key] = api_key
            save_secrets(home, secrets)
        default_port = DEFAULT_PORTS.get(provider_name, 1234)
        start = int(typer.prompt("Port range start", default=str(default_port)))
        end = int(typer.prompt("Port range end", default=str(start + 6)))
        found = await scan_local_endpoint(
            "127.0.0.1", start, end, api_key=api_key or None
        )
        if not found:
            manual = typer.prompt("Manual endpoint URL (or empty to abort)", default="")
            if not manual:
                console_print_red("no endpoint found")
                raise SystemExit(1)
            found = manual.rstrip("/")
            if not found.endswith("/v1"):
                found = f"{found}/v1"
        endpoint = found
        provider = build_provider(
            provider_name,
            endpoint=endpoint,
            api_key=api_key or None,
        )

    try:
        models = await provider.list_models()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401 and is_local_provider(provider_name):
            console_print_yellow("Server returned 401 — API key required")
            secret_key = embed_api_key_secret(provider_name)
            api_key = typer.prompt("Embed API key", hide_input=True)
            secrets[secret_key] = api_key
            save_secrets(home, secrets)
            provider = build_provider(
                provider_name,
                endpoint=endpoint,
                api_key=api_key,
            )
            models = await provider.list_models()
        else:
            raise

    embed_models = await filter_embed_models(provider, models)
    if not embed_models:
        console_print_red("no embed-capable models found")
        raise SystemExit(1)
    console.print("Models:")
    for i, m in enumerate(embed_models[:20]):
        console.print(f"  [{i}] {m}")
    idx = int(typer.prompt("Select model index", default="0"))
    model = embed_models[idx]
    dims = await provider.probe_dimensions(model)

    return EmbedSetupResult(
        provider_name=provider_name,
        model=model,
        endpoint=endpoint,
        dimensions=dims,
        provider=provider,
    )
