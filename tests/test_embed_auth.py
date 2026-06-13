"""Tests for embed provider auth."""

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
