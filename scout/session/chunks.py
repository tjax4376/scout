"""Build session embed units from file text (file-level default).

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
Updated: 2026-06-14 — default one embed unit per file/read range, not per symbol.
"""

from __future__ import annotations

SYMBOL_KINDS = {
    "module",
    "class",
    "struct",
    "interface",
    "enum",
    "function",
    "method",
    "const",
}


def _lines_overlap(
    node_start: int,
    node_end: int,
    read_start: int | None,
    read_end: int | None,
) -> bool:
    if read_start is None or read_end is None:
        return True
    return node_end >= read_start and node_start <= read_end


def _extract_lines(source: str, start_line: int, end_line: int) -> str:
    if start_line < 1:
        return ""
    lines = source.splitlines(keepends=True)
    if not lines:
        return source if start_line <= 1 else ""
    start_idx = start_line - 1
    end_idx = min(end_line, len(lines))
    if start_idx >= len(lines):
        return ""
    return "".join(lines[start_idx:end_idx])


def _build_symbol_chunks(
    rel_path: str,
    source: str,
    nodes: list[dict],
    *,
    start_line: int | None = None,
    end_line: int | None = None,
) -> list[dict]:
    chunks: list[dict] = []
    for node in nodes:
        if node.get("rel_path") != rel_path:
            continue
        kind = str(node.get("kind", ""))
        if kind not in SYMBOL_KINDS:
            continue
        ns = int(node.get("start_line") or 0)
        ne = int(node.get("end_line") or 0)
        if ns < 1 or ne < ns:
            continue
        if not _lines_overlap(ns, ne, start_line, end_line):
            continue
        text = _extract_lines(source, ns, ne)
        if not text.strip():
            continue
        chunks.append(
            {
                "node_id": node["node_id"],
                "text": text,
                "kind": kind,
                "rel_path": rel_path,
                "symbol": node.get("symbol"),
                "start_line": ns,
                "end_line": ne,
            }
        )
    return chunks


def _build_file_level_chunk(
    rel_path: str,
    source: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
) -> list[dict]:
    total_lines = max(1, len(source.splitlines()))
    read_start = start_line or 1
    read_end = end_line or total_lines
    text = _extract_lines(source, read_start, read_end)
    if not text.strip():
        return []
    return [
        {
            "node_id": f"session:{rel_path}:file",
            "text": text,
            "kind": "file",
            "rel_path": rel_path,
            "symbol": None,
            "start_line": read_start,
            "end_line": read_end,
        }
    ]


def build_file_chunks(
    rel_path: str,
    source: str,
    nodes: list[dict],
    *,
    start_line: int | None = None,
    end_line: int | None = None,
    symbol_chunks: bool = False,
) -> list[dict]:
    """One file-level embed unit by default; optional per-symbol chunks."""
    if symbol_chunks:
        symbol = _build_symbol_chunks(
            rel_path, source, nodes, start_line=start_line, end_line=end_line
        )
        if symbol:
            return symbol
    return _build_file_level_chunk(
        rel_path, source, start_line=start_line, end_line=end_line
    )
