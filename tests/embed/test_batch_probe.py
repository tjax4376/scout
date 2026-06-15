"""Tests for embed batch resolution via provider metadata."""

from __future__ import annotations

import pytest

from scout.cli.main import _parse_flags
from scout.embed.batch_probe import (
    MIN_EMBED_BATCH,
    ProviderModelLimits,
    batch_from_limits,
    compute_embed_batch_size,
    median_probe_chars,
    parse_model_limits,
    resolve_embed_batch_size,
)
from scout.embed.registry import OpenAICompatProvider
from scout.indexing import embed_texts_batched


LM_STUDIO_MODELS = {
    "data": [
        {
            "id": "text-embedding-nomic-embed-text-v1.5",
            "type": "embeddings",
            "max_context_length": 2048,
            "loaded_instances": [
                {
                    "id": "text-embedding-nomic-embed-text-v1.5",
                    "config": {
                        "context_length": 2048,
                        "eval_batch_size": 4096,
                    },
                }
            ],
        }
    ]
}


def test_parse_model_limits_lmstudio() -> None:
    limits = parse_model_limits(LM_STUDIO_MODELS, "text-embedding-nomic-embed-text-v1.5")
    assert limits is not None
    assert limits.eval_batch_size == 4096
    assert limits.context_length == 2048
    assert limits.is_embedding is True


def test_batch_from_limits_embedding_uses_hardware_ceiling() -> None:
    limits = ProviderModelLimits(
        eval_batch_size=4096,
        context_length=2048,
        is_embedding=True,
    )
    batch = batch_from_limits(limits, probe_chars=3072, hardware_ceiling=8192)
    assert batch == 8192


def test_batch_from_limits_llm_uses_eval_batch() -> None:
    limits = ProviderModelLimits(eval_batch_size=4096, context_length=2048, is_embedding=False)
    batch = batch_from_limits(limits, probe_chars=3072, hardware_ceiling=10_000)
    assert batch == 5  # 4096//768=5


def test_batch_from_limits_chunk_too_large() -> None:
    limits = ProviderModelLimits(context_length=512)
    batch = batch_from_limits(limits, probe_chars=3072, hardware_ceiling=10_000)
    assert batch == 1


def test_median_probe_chars_uses_p90() -> None:
    texts = ["a" * 100, "b" * 500, "c" * 2000, "d" * 4000]
    assert median_probe_chars(texts) == 4000


@pytest.mark.asyncio
async def test_compute_embed_batch_from_models_api(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatProvider(
        "lmstudio",
        "http://127.0.0.1:4321/v1",
        api_key="k",
    )

    async def fake_get(url: str, api_key: str | None):
        if url.endswith("/models"):
            return LM_STUDIO_MODELS
        return None

    monkeypatch.setattr("scout.embed.batch_probe._get_json", fake_get)
    batch, source = await compute_embed_batch_size(
        provider,
        "text-embedding-nomic-embed-text-v1.5",
        probe_chars=3072,
        dimensions=768,
    )
    assert batch >= MIN_EMBED_BATCH
    assert "embedding model" in source


@pytest.mark.asyncio
async def test_resolve_embed_batch_uses_cache_without_reprobe() -> None:
    provider = OpenAICompatProvider("lmstudio", "http://127.0.0.1:4321/v1")
    batch = await resolve_embed_batch_size(
        provider,
        "model",
        768,
        ["x" * 100],
        cached=8192,
        reprobe=False,
    )
    assert batch == 8192


@pytest.mark.asyncio
async def test_embed_texts_batched_uses_batch_size() -> None:
    batch_sizes: list[int] = []

    class Provider:
        async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
            batch_sizes.append(len(texts))
            return [[float(i)] for i in range(len(texts))]

    texts = [f"chunk-{i}" for i in range(10)]
    await embed_texts_batched(Provider(), "model", texts, batch_size=4, console=None)
    assert batch_sizes == [4, 4, 2]


def test_parse_flags_embed_batch_auto_default() -> None:
    _, _, _, _, embed_batch, reprobe = _parse_flags(["scout", "reindex"])
    assert embed_batch == 0
    assert reprobe is False
