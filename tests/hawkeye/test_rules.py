"""Rule engine tests."""

from __future__ import annotations

from scout.hawkeye.rules.engine import ReviewContext, evaluate_rules
from scout.hawkeye.rules.globs import path_matches


def test_path_matches_auth_glob() -> None:
    assert path_matches("**/auth/**", "src/auth/login.py")
    assert not path_matches("**/auth/**", "src/api/app.py")


def test_staleness_gate_fires() -> None:
    rules = [
        {
            "id": "HKY-AUTH-005",
            "type": "staleness_gate",
            "severity": "error",
            "path_glob": "**/auth/**",
            "message": "stale",
        }
    ]
    ctx = ReviewContext(
        session_id="s1",
        space="sp",
        changed_lines={"src/auth/x.py": {1}},
        symbols_by_prefix={},
        changed_symbols=[],
        neighbors_by_node={},
        file_text={},
        stale=True,
    )
    findings = evaluate_rules(rules, [], ctx)
    assert len(findings) == 1
    assert findings[0].rule_id == "HKY-AUTH-005"


def test_graph_neighbor_missing_test_caller() -> None:
    rules = [
        {
            "id": "HKY-API-003",
            "type": "graph_neighbor",
            "severity": "warning",
            "path_glob": "**/api/**",
            "kinds": ["function"],
            "edge": "Calls",
            "direction": "incoming",
            "from_path_glob": "tests/**",
            "min_count": 1,
            "on": "changed_symbol",
            "message": "no test caller",
        }
    ]
    sym = {
        "node_id": "abc",
        "rel_path": "scout/api/app.py",
        "start_line": 300,
        "end_line": 350,
        "kind": "function",
        "symbol": "graph_search",
    }
    ctx = ReviewContext(
        session_id="s1",
        space="sp",
        changed_lines={"scout/api/app.py": {310}},
        symbols_by_prefix={},
        changed_symbols=[sym],
        neighbors_by_node={"abc": [{"edge": "Calls", "rel_path": "scout/cli/main.py"}]},
        file_text={},
        neighbors_logged=set(),
    )
    findings = evaluate_rules(rules, [], ctx)
    assert any(f.rule_id == "HKY-API-003" for f in findings)
    assert "abc" in ctx.neighbors_logged


def test_text_hunk_raw_sql() -> None:
    rules = [
        {
            "id": "HKY-API-005",
            "type": "text_hunk",
            "severity": "warning",
            "path_glob": "**/api/**",
            "pattern": "(?i)raw\\s*sql",
            "message": "raw sql",
        }
    ]
    sym = {
        "node_id": "n1",
        "rel_path": "scout/api/db.py",
        "start_line": 1,
        "end_line": 10,
        "kind": "function",
    }
    ctx = ReviewContext(
        session_id="s1",
        space="sp",
        changed_lines={"scout/api/db.py": {2}},
        symbols_by_prefix={},
        changed_symbols=[sym],
        neighbors_by_node={},
        file_text={"scout/api/db.py": "def q():\n    raw sql = True\n"},
    )
    findings = evaluate_rules(rules, [], ctx)
    assert len(findings) == 1


def test_anti_pattern_ref_resolves() -> None:
    rules = [
        {
            "id": "HKY-REF-001",
            "type": "anti_pattern_ref",
            "severity": "error",
            "anti_pattern_id": "AP-HARDCODED-SECRET",
            "path_glob": "**/auth/**",
        }
    ]
    antipatterns = [
        {
            "id": "AP-HARDCODED-SECRET",
            "type": "text_regex",
            "severity": "error",
            "path_glob": "**/auth/**",
            "pattern": "(?i)password\\s*=\\s*[\"'][^\"']+[\"']",
            "message": "hardcoded secret",
        }
    ]
    ctx = ReviewContext(
        session_id="s1",
        space="sp",
        changed_lines={"src/auth/login.py": {10}},
        symbols_by_prefix={},
        changed_symbols=[],
        neighbors_by_node={},
        file_text={"src/auth/login.py": 'password = "supersecret123"\n'},
    )
    findings = evaluate_rules(rules, antipatterns, ctx)
    assert len(findings) == 1
    assert findings[0].message == "hardcoded secret"


def test_path_matches_windows_backslash() -> None:
    assert path_matches("**/auth/**", "src\\auth\\login.py")
