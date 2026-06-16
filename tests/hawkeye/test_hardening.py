"""CLI semantics and I/O hardening tests."""

from __future__ import annotations

import json
import shutil
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import yaml

from scout.hawkeye.__main__ import (
    EXIT_FINDINGS,
    EXIT_RUNTIME,
    EXIT_SUCCESS,
    _cached_load_config,
    cmd_export_sarif,
    cmd_mine,
    cmd_replay,
    main,
)
from scout.hawkeye.hybrid.escalate import MAX_ESCALATION_BYTES, write_escalation
from scout.hawkeye.learning.promote import promote_candidate
from scout.hawkeye.runner.playbook import ReviewResult
from scout.hawkeye.runner.diff_scope import DiffScope


def _write_min_config(cfg_dir: Path) -> None:
    traces = cfg_dir / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "scout_api": "http://127.0.0.1:8741/v1",
                "default_space": "myapp",
                "trace_dir": str(traces),
            }
        )
    )
    (cfg_dir / "rules.yaml").write_text("rules: []\n")
    (cfg_dir / "antipatterns.yaml").write_text("antipatterns: []\n")


def test_main_unknown_command_returns_runtime() -> None:
    with patch("scout.hawkeye.__main__.build_parser") as mock_parser:
        mock_parser.return_value.parse_args.return_value = Namespace(command="nope")
        assert main([]) == EXIT_RUNTIME


def test_export_sarif_missing_trace_exits_runtime(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    _write_min_config(cfg_dir)
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        args = Namespace(
            session="missing",
            output=tmp_path / "out.sarif",
            project=False,
            project_root=tmp_path,
            rules=None,
            antipatterns=None,
        )
        assert cmd_export_sarif(args) == EXIT_RUNTIME
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig


def test_replay_mismatch_exits_findings(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    _write_min_config(cfg_dir)
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        args = Namespace(
            session="sess",
            dry_run=False,
            project=False,
            project_root=tmp_path,
            rules=None,
            antipatterns=None,
        )
        with patch("scout.hawkeye.__main__.replay_session") as mock_replay:
            mock_replay.return_value = type("R", (), {"match": False})()
            with patch("scout.hawkeye.__main__.print_replay_report", return_value="report"):
                assert cmd_replay(args) == EXIT_FINDINGS
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig


def test_cached_load_config_single_read(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    _write_min_config(cfg_dir)
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    _cached_load_config.cache_clear()
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        with patch("scout.hawkeye.__main__.load_config", wraps=cfg_mod.load_config) as mock_load:
            _cached_load_config(str(tmp_path.resolve()), False, None, None, False)
            _cached_load_config(str(tmp_path.resolve()), False, None, None, False)
            assert mock_load.call_count == 1
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig
        _cached_load_config.cache_clear()


def test_escalation_truncation(tmp_path: Path) -> None:
    huge_hunks = [
        {
            "rel_path": f"f{i}.py",
            "line_ranges": [{"start_line": 1, "end_line": 99999}],
            "note": "x" * 2000,
        }
        for i in range(10000)
    ]
    bundle = {
        "session_id": "s",
        "mapped_findings_count": 0,
        "unmapped_hunks": huge_hunks,
        "trace_summary": {"steps": 0},
    }
    out = tmp_path / "esc.json"
    write_escalation(out, bundle)
    assert out.stat().st_size <= MAX_ESCALATION_BYTES + 1024
    payload = json.loads(out.read_text())
    assert payload.get("_truncated") is True


def test_promote_creates_backup(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("rules:\n  - id: R1\n    type: path_glob\n    severity: warning\n    path_glob: '**'\n")
    candidates_path = tmp_path / "candidates.yaml"
    candidates_path.write_text(
        yaml.safe_dump(
            {
                "candidates": [
                    {
                        "candidate_id": "CAND-001",
                        "suggested_rule": {
                            "id": "R2",
                            "type": "path_glob",
                            "severity": "warning",
                            "path_glob": "**",
                        },
                    }
                ]
            }
        )
    )
    promote_candidate(rules_path, candidates_path, "CAND-001", approve=True)
    assert (tmp_path / "rules.yaml.bak").is_file()


def test_mine_pagination(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod
    from scout.hawkeye.trace.store import TraceStore

    cfg_dir = tmp_path / ".hawkeye"
    traces = cfg_dir / "traces"
    traces.mkdir(parents=True)
    _write_min_config(cfg_dir)
    for idx in range(3):
        store = TraceStore(traces, f"s{idx}")
        store.append(
            {
                "type": "finding",
                "finding": {"rule_id": "R", "severity": "warning", "scout": {}},
            }
        )

    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        args = Namespace(
            threshold=1,
            output=None,
            limit=1,
            offset=1,
            batch_size=None,
            project=False,
            project_root=tmp_path,
        )
        assert cmd_mine(args) == EXIT_SUCCESS
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig
