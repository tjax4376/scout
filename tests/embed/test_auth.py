"""Tests for embed provider auth."""

from scout.config import get_embed_api_key
from scout.embed.registry import OpenAICompatProvider, _auth_headers


def test_auth_headers_with_key() -> None:
    headers = _auth_headers("sk-test")
    assert headers == {"Authorization": "Bearer sk-test"}


def test_auth_headers_without_key() -> None:
    assert _auth_headers(None) == {}
    assert _auth_headers("") == {}


def test_openai_compat_provider_stores_key() -> None:
    p = OpenAICompatProvider("lmstudio", "http://127.0.0.1:1234/v1", api_key="abc")
    assert p._headers() == {"Authorization": "Bearer abc"}


def test_get_embed_api_key_selects_provider_key() -> None:
    """Each provider must use its own secret, not openrouter_api_key fallback."""
    secrets = {"openrouter_api_key": "or-key", "lmstudio_api_key": "lm-key"}
    assert get_embed_api_key(secrets, "lmstudio") == "lm-key"
    assert get_embed_api_key(secrets, "openrouter") == "or-key"
