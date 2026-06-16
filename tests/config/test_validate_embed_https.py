"""Tests for embed endpoint HTTPS validation."""

from __future__ import annotations

import pytest

from scout.config import EmbedConfig, ScoutConfig, validate_embed


def test_validate_embed_rejects_remote_http() -> None:
    config = ScoutConfig(
        embed=EmbedConfig(
            provider="openrouter",
            model="x",
            endpoint="http://api.example.com/v1",
            dimensions=8,
        )
    )
    with pytest.raises(ValueError, match="https"):
        validate_embed(config)


def test_validate_embed_allows_localhost_http() -> None:
    config = ScoutConfig(
        embed=EmbedConfig(
            provider="lmstudio",
            model="x",
            endpoint="http://127.0.0.1:1234/v1",
            dimensions=8,
        )
    )
    assert validate_embed(config).provider == "lmstudio"
