"""Session embed chunk builder tests."""

from __future__ import annotations

from scout.session.chunks import build_file_chunks


def test_build_file_chunks_defaults_to_whole_file() -> None:
    source = "line1\nline2\nline3\n"
    nodes = [
        {
            "node_id": "n1",
            "kind": "function",
            "rel_path": "src/auth.py",
            "symbol": "login",
            "start_line": 1,
            "end_line": 1,
        },
        {
            "node_id": "n2",
            "kind": "function",
            "rel_path": "src/auth.py",
            "symbol": "logout",
            "start_line": 2,
            "end_line": 2,
        },
    ]
    chunks = build_file_chunks("src/auth.py", source, nodes)
    assert len(chunks) == 1
    assert chunks[0]["kind"] == "file"
    assert chunks[0]["text"] == source
    assert chunks[0]["node_id"] == "session:src/auth.py:file"


def test_build_file_chunks_respects_read_range() -> None:
    source = "a\nb\nc\n"
    chunks = build_file_chunks("x.py", source, [], start_line=2, end_line=2)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "b\n"
    assert chunks[0]["start_line"] == 2
    assert chunks[0]["end_line"] == 2


def test_build_file_chunks_symbol_mode() -> None:
    source = "def one():\n    pass\n\ndef two():\n    pass\n"
    nodes = [
        {
            "node_id": "n1",
            "kind": "function",
            "rel_path": "m.py",
            "symbol": "one",
            "start_line": 1,
            "end_line": 2,
        },
        {
            "node_id": "n2",
            "kind": "function",
            "rel_path": "m.py",
            "symbol": "two",
            "start_line": 4,
            "end_line": 5,
        },
    ]
    chunks = build_file_chunks("m.py", source, nodes, symbol_chunks=True)
    assert len(chunks) == 2
    assert chunks[0]["symbol"] == "one"
    assert chunks[1]["symbol"] == "two"
