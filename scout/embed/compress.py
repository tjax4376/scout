"""Deterministic chunk text compression before embed.

Metadata: v0.1.1 | Scout Contributors | 2026-06-14
Change: reduce embed token count; stored text matches embedded form.
"""

from __future__ import annotations

import re

from scout.config import EmbedConfig

_BLANK_RUN = re.compile(r"\n{3,}")


def _strip_line_comments_line(line: str) -> str:
    """Remove full-line # or // comments (heuristic; skips inline code)."""
    trimmed = line.lstrip()
    if trimmed.startswith("#") or trimmed.startswith("//"):
        return ""
    return line


def compress_chunk_text(text: str, *, strip_line_comments: bool = False) -> str:
    """Lossy text reduction for embed input — not byte compression."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if strip_line_comments:
        lines = [_strip_line_comments_line(line) for line in lines]

    lines = [line.rstrip() for line in lines]
    joined = "\n".join(lines)
    joined = _BLANK_RUN.sub("\n\n", joined)
    return joined.strip("\n")


def prepare_chunks_for_embed(chunks: list[dict], embed: EmbedConfig) -> list[dict]:
    """Apply compression to chunk dicts in place; return same list."""
    if not embed.compress_chunks:
        return chunks
    for chunk in chunks:
        raw = chunk.get("text") or ""
        chunk["text"] = compress_chunk_text(
            raw,
            strip_line_comments=embed.compress_strip_line_comments,
        )
    return chunks
