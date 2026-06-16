"""CLI hardening tests."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import yaml

from scout.hawkeye.__main__ import _safe_int, cmd_export_sarif, main


def test_safe_int_defaults() -> None:
    assert _safe_int(None, 1) == 1
    assert _safe_int("42", 1) == 42
    assert _safe_int("bad", 7) == 7


def test_main_unknown_command() -> None:
    from scout.hawkeye.__main__ import EXIT_RUNTIME

    with patch("scout.hawkeye.__main__.build_parser") as mock_parser:
        mock_parser.return_value.parse_args.return_value = Namespace(command="nope")
        assert main([]) == EXIT_RUNTIME


def test_export_sarif_malformed_lines(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    traces = cfg_dir / "traces"
    traces.mkdir(parents=True)
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

    session_id = "test-session"
    finding = {
        "type": "finding",
        "session_id": session_id,
        "timestamp": "2026-06-15T00:00:00+00:00",
        "finding": {
            "finding_id": "f1",
            "rule_id": "R1",
            "severity": "warning",
            "message": "msg",
            "rel_path": "a.py",
            "start_line": "not-a-number",
            "end_line": None,
            "scout": {},
            "hawkeye": {"session_id": session_id, "mapped": True},
        },
    }
    (traces / f"{session_id}.jsonl").write_text(json.dumps(finding) + "\n")

    orig_global = cfg_mod.GLOBAL_HAWKEYE_DIR
    out = tmp_path / "out.sarif"
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        args = Namespace(
            session=session_id,
            output=out,
            project=False,
            project_root=tmp_path,
            rules=None,
            antipatterns=None,
        )
        assert cmd_export_sarif(args) == 0
        payload = json.loads(out.read_text())
        region = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
        assert region["startLine"] == 1
        assert region["endLine"] == 1
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig_global
