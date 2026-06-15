"""Tests for optional embed setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from scout.config import ScoutConfig
from scout.setup.embed import configure_embed


@pytest.mark.asyncio
async def test_configure_embed_local_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ScoutConfig()
    secrets: dict[str, str] = {}
    provider = AsyncMock()
    provider.list_models = AsyncMock(return_value=["text-embedding-test"])
    provider.probe_dimensions = AsyncMock(return_value=384)

    prompts = iter(["local", "lmstudio", "", "4321", "4327", "0"])

    def fake_prompt(msg: str, default: str = "", **kwargs: object) -> str:
        return next(prompts)

    monkeypatch.setattr("scout.setup.embed.typer.prompt", fake_prompt)
    monkeypatch.setattr(
        "scout.setup.embed.scan_local_endpoint",
        AsyncMock(return_value="http://127.0.0.1:4321/v1"),
    )
    monkeypatch.setattr(
        "scout.setup.embed.filter_embed_models",
        AsyncMock(return_value=["text-embedding-test"]),
    )
    monkeypatch.setattr(
        "scout.setup.embed.build_provider",
        lambda *a, **k: provider,
    )

    result = await configure_embed("/tmp/.scout", secrets, config, MagicMock())
    assert result.provider_name == "lmstudio"
    assert result.endpoint == "http://127.0.0.1:4321/v1"
    assert result.dimensions == 384
