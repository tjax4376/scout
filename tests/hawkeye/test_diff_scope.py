"""Diff scope and symbol overlap tests."""

from __future__ import annotations

from scout.hawkeye.runner.diff_scope import derive_path_prefixes, map_changed_symbols, parse_diff_output


SAMPLE_DIFF = """diff --git a/scout/api/app.py b/scout/api/app.py
--- a/scout/api/app.py
+++ b/scout/api/app.py
@@ -10,1 +10,3 @@
+import logging
+import os
"""


def test_parse_diff_output_lines() -> None:
    scope = parse_diff_output(SAMPLE_DIFF, "HEAD~1")
    assert "scout/api/app.py" in scope.changed_paths
    assert 10 in scope.changed_lines["scout/api/app.py"]
    assert 11 in scope.changed_lines["scout/api/app.py"]
    assert "scout/api/" in scope.path_prefixes


def test_derive_path_prefixes() -> None:
    prefixes = derive_path_prefixes(["src/auth/login.py"])
    assert "src/" in prefixes
    assert "src/auth/" in prefixes


def test_map_changed_symbols() -> None:
    symbols = [
        {
            "node_id": "n1",
            "rel_path": "src/auth.py",
            "start_line": 5,
            "end_line": 20,
            "kind": "function",
        }
    ]
    changed = {"src/auth.py": {10}}
    mapped = map_changed_symbols(symbols, changed)
    assert len(mapped) == 1
