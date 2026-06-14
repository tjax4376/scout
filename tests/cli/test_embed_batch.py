"""Tests for --embed-batch CLI flag and batched embedding."""

from __future__ import annotations

import pytest

from scout.cli.main import _parse_flags
from scout.indexing import DEFAULT_EMBED_BATCH, embed_texts_batched


def test_parse_flags_embed_batch_default() -> None:
    positional, force, agent, top_k, embed_batch = _parse_flags(
        ["scout", "reindex"]
    )
    assert positional == ["scout", "reindex"]
    assert force is False
    assert agent is None
    assert top_k == 10
    assert embed_batch == DEFAULT_EMBED_BATCH


def test_parse_flags_embed_batch_custom() -> None:
    _, _, _, _, embed_batch = _parse_flags(
        ["scout", "reindex", "--embed-batch", "128", "--force"]
    )
    assert embed_batch == 128


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
