"""Tests for embed chunk compression."""

from __future__ import annotations

from scout.config import EmbedConfig
from scout.embed.compress import compress_chunk_text, prepare_chunks_for_embed


def test_compress_empty_input() -> None:
    assert compress_chunk_text("") == ""


def test_compress_trailing_whitespace_and_blank_lines() -> None:
    raw = "def foo():\n    x = 1   \n\n\n\n    return x\n"
    out = compress_chunk_text(raw)
    assert "   \n" not in out
    assert "\n\n\n" not in out
    assert "def foo():" in out


def test_compress_strip_line_comments_off_preserves_hash() -> None:
    raw = "# header comment\ndef foo():\n    pass\n"
    out = compress_chunk_text(raw, strip_line_comments=False)
    assert "# header comment" in out


def test_compress_strip_line_comments_on() -> None:
    raw = "# header comment\ndef foo():\n    pass\n// tail\n"
    out = compress_chunk_text(raw, strip_line_comments=True)
    assert "# header" not in out
    assert "// tail" not in out
    assert "def foo():" in out


def test_compress_preserves_inline_url_with_slashes() -> None:
    raw = 'url = "http://example.com"\n'
    out = compress_chunk_text(raw, strip_line_comments=True)
    assert "http://example.com" in out


def test_prepare_chunks_for_embed_disabled() -> None:
    chunks = [{"text": "  hello  \n\n\nworld  "}]
    embed = EmbedConfig(compress_chunks=False)
    prepare_chunks_for_embed(chunks, embed)
    assert chunks[0]["text"] == "  hello  \n\n\nworld  "


def test_prepare_chunks_for_embed_enabled() -> None:
    chunks = [{"text": "  hello  \n\n\nworld  "}]
    embed = EmbedConfig(compress_chunks=True)
    prepare_chunks_for_embed(chunks, embed)
    assert chunks[0]["text"] == "  hello\n\nworld"
