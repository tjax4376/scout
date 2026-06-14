"""Resolve embed batch size from provider metadata (no embed spam).

Metadata: v0.1.0 | Scout Contributors | 2026-06-13
Rationale: LM Studio and similar servers expose context_length and eval_batch_size
on GET /models — derive batch from that + chunk size instead of trial requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from scout.embed.registry import EmbedProvider, OpenAICompatProvider, OpenRouterProvider, _auth_headers
from scout.prescan.runner import _available_ram_bytes

DEFAULT_PROBE_CHARS = 3072
MIN_EMBED_BATCH = 64
PROBE_BATCH_CAP = 131_072
RAM_FRACTION_FOR_EMBED_BATCH = 0.15
CHARS_PER_TOKEN = 4


@dataclass
class ProviderModelLimits:
    max_context_length: int | None = None
    context_length: int | None = None
    eval_batch_size: int | None = None
    is_embedding: bool = False


def hardware_batch_ceiling(
    *,
    probe_chars: int = DEFAULT_PROBE_CHARS,
    dimensions: int = 768,
    available_ram_bytes: int | None = None,
) -> int:
    """Upper bound from available host RAM."""
    ram = available_ram_bytes if available_ram_bytes is not None else _available_ram_bytes()
    bytes_per_chunk = max(probe_chars * 2, 512) + (dimensions * 4)
    budget = int(ram * RAM_FRACTION_FOR_EMBED_BATCH)
    return max(MIN_EMBED_BATCH, min(budget // bytes_per_chunk, PROBE_BATCH_CAP))


def median_probe_chars(texts: list[str]) -> int:
    """Representative chunk size from indexed texts (p90 length)."""
    if not texts:
        return DEFAULT_PROBE_CHARS
    lengths = sorted(len(t) for t in texts)
    idx = min(int(len(lengths) * 0.9), len(lengths) - 1)
    p90 = lengths[idx]
    return min(max(p90, 256), 12_288)


def estimate_tokens(char_count: int) -> int:
    return max(1, (char_count + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _model_matches(entry: dict[str, Any], model_id: str) -> bool:
    needle = model_id.lower()
    candidates = [
        entry.get("id"),
        entry.get("key"),
        entry.get("display_name"),
    ]
    for inst in entry.get("loaded_instances", []) or []:
        candidates.append(inst.get("id"))
    for raw in candidates:
        if not raw:
            continue
        hay = str(raw).lower()
        if hay == needle or needle in hay or hay in needle:
            return True
    return False


def parse_model_limits(payload: dict[str, Any], model_id: str) -> ProviderModelLimits | None:
    """Extract limits from OpenAI-compat or LM Studio models JSON."""
    items = payload.get("data")
    if not isinstance(items, list):
        return None

    entry: dict[str, Any] | None = None
    for item in items:
        if isinstance(item, dict) and _model_matches(item, model_id):
            entry = item
            break
    if entry is None:
        return None

    limits = ProviderModelLimits(
        max_context_length=_positive_int(entry.get("max_context_length")),
        is_embedding=str(entry.get("type", "")).lower() in {"embedding", "embeddings"},
    )
    for inst in entry.get("loaded_instances", []) or []:
        if not isinstance(inst, dict):
            continue
        cfg = inst.get("config") or {}
        if not isinstance(cfg, dict):
            continue
        limits.context_length = _positive_int(cfg.get("context_length")) or limits.context_length
        limits.eval_batch_size = _positive_int(cfg.get("eval_batch_size")) or limits.eval_batch_size

    if any((limits.max_context_length, limits.context_length, limits.eval_batch_size)):
        return limits
    return None


def _positive_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def batch_from_limits(
    limits: ProviderModelLimits,
    probe_chars: int,
    hardware_ceiling: int,
) -> int:
    """Compute batch count from server-reported limits + chunk token estimate."""
    tokens_per_chunk = estimate_tokens(probe_chars)
    per_input_ctx = limits.context_length or limits.max_context_length

    if per_input_ctx and per_input_ctx < tokens_per_chunk:
        return 1

    # LM Studio: eval_batch_size applies to LLM inference only, not embeddings.
    if limits.is_embedding:
        return max(MIN_EMBED_BATCH, min(hardware_ceiling, PROBE_BATCH_CAP))

    if limits.eval_batch_size:
        batch = limits.eval_batch_size // tokens_per_chunk
        return max(MIN_EMBED_BATCH, min(batch, hardware_ceiling, PROBE_BATCH_CAP))

    if per_input_ctx:
        batch = per_input_ctx // tokens_per_chunk
        return max(MIN_EMBED_BATCH, min(batch, hardware_ceiling, PROBE_BATCH_CAP))

    return max(MIN_EMBED_BATCH, min(hardware_ceiling, PROBE_BATCH_CAP))


async def _get_json(url: str, api_key: str | None) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=_auth_headers(api_key))
            resp.raise_for_status()
            data = resp.json()
        return data if isinstance(data, dict) else None
    except httpx.HTTPError:
        return None


def _lmstudio_native_models_url(endpoint: str) -> str | None:
    # http://127.0.0.1:4321/v1 -> http://127.0.0.1:4321/api/v1/models
    parsed = urlparse(endpoint.rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/api/v1/models"


async def fetch_provider_limits(
    provider: EmbedProvider,
    model: str,
) -> ProviderModelLimits | None:
    """GET /models (and LM Studio native API) — no embedding requests."""
    urls: list[str] = []

    if isinstance(provider, OpenAICompatProvider):
        urls.append(f"{provider.endpoint}/models")
        if provider.name == "lmstudio":
            native = _lmstudio_native_models_url(provider.endpoint)
            if native:
                urls.append(native)
        api_key = provider.api_key
    elif isinstance(provider, OpenRouterProvider):
        urls.append(f"{provider.base}/models")
        api_key = provider.api_key
    else:
        return None

    merged = ProviderModelLimits()
    for url in urls:
        payload = await _get_json(url, api_key)
        if not payload:
            continue
        limits = parse_model_limits(payload, model)
        if not limits:
            continue
        merged.max_context_length = merged.max_context_length or limits.max_context_length
        merged.context_length = merged.context_length or limits.context_length
        merged.eval_batch_size = merged.eval_batch_size or limits.eval_batch_size
        merged.is_embedding = merged.is_embedding or limits.is_embedding

    if any((merged.max_context_length, merged.context_length, merged.eval_batch_size)):
        return merged
    return None


async def compute_embed_batch_size(
    provider: EmbedProvider,
    model: str,
    *,
    probe_chars: int = DEFAULT_PROBE_CHARS,
    dimensions: int = 768,
) -> tuple[int, str]:
    """Return (batch_size, source_description)."""
    hw = hardware_batch_ceiling(probe_chars=probe_chars, dimensions=dimensions)
    limits = await fetch_provider_limits(provider, model)
    if limits:
        batch = batch_from_limits(limits, probe_chars, hw)
        parts = []
        if limits.eval_batch_size:
            parts.append(f"eval_batch_size={limits.eval_batch_size}")
        if limits.is_embedding:
            parts.append("embedding model")
        ctx = limits.context_length or limits.max_context_length
        if ctx:
            parts.append(f"context={ctx}")
        detail = ", ".join(parts) if parts else "models API"
        return batch, f"provider metadata ({detail})"
    return max(MIN_EMBED_BATCH, min(hw, 4096)), "host RAM estimate (no provider limits in /models)"


async def resolve_embed_batch_size(
    provider: EmbedProvider,
    model: str,
    dimensions: int,
    texts: list[str],
    *,
    cli_override: int = 0,
    cached: int = 0,
    reprobe: bool = False,
) -> int:
    """Resolve batch size: CLI override > cached config > models API metadata."""
    if cli_override > 0:
        return cli_override
    if cached > 0 and not reprobe:
        return cached
    probe_chars = median_probe_chars(texts)
    batch, _source = await compute_embed_batch_size(
        provider,
        model,
        probe_chars=probe_chars,
        dimensions=dimensions,
    )
    return batch
