"""Setup discovery and path review integration tests."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import yaml

from scout.hawkeye.__main__ import EXIT_RUNTIME, EXIT_SUCCESS, cmd_setup


def test_cmd_setup_scout_not_found(tmp_path: Path) -> None:
    with patch("scout.hawkeye.__main__.prepare_setup") as mock_prepare:
        mock_prepare.side_effect = ValueError("Scout API not found — start Scout with `scout serve`")
        args = Namespace(
            scout_api=None,
            space=None,
            project=False,
            project_root=tmp_path,
            rules_file=None,
            antipatterns_file=None,
            force=True,
            yes=True,
        )
        assert cmd_setup(args) == EXIT_RUNTIME


def test_path_review_integration(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod
    from scout.hawkeye.runner.playbook import run_review
    from scout.hawkeye.runner.path_scope import file_scope
    from scout.hawkeye.setup_cmd import run_setup

    cfg_dir = tmp_path / ".hawkeye"
    repo = tmp_path / "repo"
    target = repo / "scout" / "api" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("def create_app():\n    pass\n")

    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        run_setup(
            scout_api="http://127.0.0.1:8741/v1",
            space="myapp",
            force=True,
        )
        overlay = cfg_dir / "overlay-rules.yaml"
        overlay.write_text(
            yaml.safe_dump(
                {
                    "rules": [
                        {
                            "id": "PATH-001",
                            "type": "path_glob",
                            "severity": "warning",
                            "path_glob": "scout/api/**",
                            "message": "api touched",
                        }
                    ]
                }
            )
        )
        rules = yaml.safe_load((cfg_dir / "rules.yaml").read_text())
        rules["rules"].append(
            {
                "id": "PATH-001",
                "type": "path_glob",
                "severity": "warning",
                "path_glob": "scout/api/**",
                "message": "api touched",
            }
        )
        (cfg_dir / "rules.yaml").write_text(yaml.safe_dump(rules))

        symbols = [
            {
                "node_id": "node1",
                "rel_path": "scout/api/app.py",
                "start_line": 1,
                "end_line": 10,
                "kind": "function",
                "symbol": "create_app",
            }
        ]

        class FakeBackend:
            name = "graph"
            stale = False

            def __init__(self) -> None:
                self.repo_root = repo

            def list_symbols(self, path_prefix=""):
                return symbols

            def neighbors(self, node_id, *, depth=2, max_nodes=50):
                return []

            def read_file(self, rel_path, *, start_line=None, end_line=None):
                return target.read_text()

        scope = file_scope(repo, target)
        with patch(
            "scout.hawkeye.runner.playbook.resolve_backend",
            return_value=(FakeBackend(), "graph", "myapp"),
        ):
            cfg = cfg_mod.load_config()
            result = run_review(cfg, scope=scope, repo_root=repo, backend_mode="graph")

        assert result.findings
        assert any(f.rule_id == "PATH-001" for f in result.findings)
        assert result.trace_path.exists()
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig
