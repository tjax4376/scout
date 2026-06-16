"""SARIF and integration-style tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from scout.hawkeye.findings.schema import Finding, GraphEvidence, findings_hash
from scout.hawkeye.findings.sarif import findings_to_sarif, write_sarif


def test_sarif_structure() -> None:
    findings = [
        Finding(
            rule_id="HKY-AUTH-003",
            severity="warning",
            message="no test caller",
            rel_path="src/auth.py",
            start_line=10,
            end_line=20,
            session_id="sess-1",
            scout=GraphEvidence(
                node_id="n1",
                identification_method="rule:HKY-AUTH-003",
            ),
        )
    ]
    sarif = findings_to_sarif(findings)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "hawkeye"
    assert run["results"][0]["ruleId"] == "HKY-AUTH-003"
    assert run["results"][0]["properties"]["scout"]["node_id"] == "n1"


def test_findings_hash_stable() -> None:
    a = [
        Finding(rule_id="R", severity="warning", message="m", rel_path="a.py"),
        Finding(rule_id="R2", severity="error", message="m2", rel_path="b.py"),
    ]
    b = list(reversed(a))
    assert findings_hash(a) == findings_hash(b)


def test_write_sarif_nested_directory(tmp_path: Path) -> None:
    findings = [
        Finding(rule_id="R", severity="warning", message="m", rel_path="a.py", session_id="s")
    ]
    out = tmp_path / "nested" / "dir" / "out.sarif"
    write_sarif(out, findings)
    assert out.is_file()


def test_integration_review_with_mock_scout(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod
    from scout.hawkeye.runner.playbook import run_review
    from scout.hawkeye.setup_cmd import run_setup

    cfg_dir = tmp_path / ".hawkeye"
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
    run_setup(
        scout_api="http://127.0.0.1:8741/v1",
        space="myapp",
        force=True,
    )

    diff_text = """diff --git a/scout/api/app.py b/scout/api/app.py
--- a/scout/api/app.py
+++ b/scout/api/app.py
@@ -1,1 +1,2 @@
+x = 1
"""

    symbols = [
        {
            "node_id": "node1",
            "rel_path": "scout/api/app.py",
            "start_line": 1,
            "end_line": 100,
            "kind": "function",
            "symbol": "create_app",
        }
    ]
    neighbors = [{"edge": "Calls", "rel_path": "scout/cli/main.py"}]

    class FakeBackend:
        name = "graph"
        stale = False

        def __init__(self) -> None:
            self.repo_root = repo

        def list_symbols(self, path_prefix=""):
            return symbols

        def neighbors(self, node_id, *, depth=2, max_nodes=50):
            return neighbors

        def read_file(self, rel_path, *, start_line=None, end_line=None):
            return "def create_app():\n    pass\n"

    with patch("scout.hawkeye.runner.playbook.git_diff_scope") as mock_diff:
        from scout.hawkeye.runner.diff_scope import parse_diff_output

        mock_diff.return_value = parse_diff_output(diff_text, "HEAD~1")
        with patch(
            "scout.hawkeye.runner.playbook.resolve_backend",
            return_value=(FakeBackend(), "graph", "myapp"),
        ):
            cfg = cfg_mod.load_config()
            result = run_review(cfg, diff_ref="HEAD~1", repo_root=repo, backend_mode="graph")

    assert result.session_id
    assert result.trace_path.exists()
    sarif_path = tmp_path / "out.sarif"
    write_sarif(sarif_path, result.findings)
    assert sarif_path.is_file()

    # reload config validates yaml still ok
    rules = yaml.safe_load((cfg_dir / "rules.yaml").read_text())
    assert len(rules["rules"]) >= 10
