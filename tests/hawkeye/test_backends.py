"""Review backend selection and filesystem playbook tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import yaml

from scout.hawkeye.backends.filesystem import FilesystemReviewBackend
from scout.hawkeye.backends.resolve import filter_rules_for_backend, resolve_backend
from scout.hawkeye.config import HawkeyeConfig, load_config_or_defaults
from scout.hawkeye.runner.path_scope import file_scope
from scout.hawkeye.runner.playbook import run_review
from scout.hawkeye.trace.store import TraceStore


def test_filter_rules_skips_graph_only_in_filesystem() -> None:
    rules = [
        {"id": "G1", "type": "graph_neighbor", "severity": "warning"},
        {"id": "S1", "type": "staleness_gate", "severity": "error"},
        {"id": "T1", "type": "text_hunk", "severity": "warning"},
    ]
    kept, skipped = filter_rules_for_backend(rules, "filesystem")
    assert [r["id"] for r in kept] == ["T1"]
    assert skipped == ["G1", "S1"]


def test_filesystem_backend_reads_local_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n")
    trace = TraceStore(tmp_path / "traces", "sess-fs")
    backend = FilesystemReviewBackend(repo_root=repo, trace=trace)
    assert backend.list_symbols() == []
    assert backend.neighbors("node") == []
    assert backend.read_file("src/app.py") == "print('hello')\n"
    assert backend.stale is False


def test_filesystem_review_no_http(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    auth = repo / "src" / "auth" / "login.py"
    auth.parent.mkdir(parents=True)
    auth.write_text('API_KEY = "hardcoded-secret"\n')

    cfg = HawkeyeConfig(
        scout_api="",
        default_space="local",
        config_dir=tmp_path / ".hawkeye",
        trace_dir=tmp_path / "traces",
        rules=[
            {
                "id": "FS-SECRET",
                "type": "anti_pattern_ref",
                "severity": "error",
                "anti_pattern_id": "AP-HARDCODED-SECRET",
                "path_glob": "**/auth/**",
                "message": "secret in auth",
            }
        ],
        antipatterns=[
            {
                "id": "AP-HARDCODED-SECRET",
                "type": "text_regex",
                "severity": "error",
                "pattern": "(?i)(api[_-]?key|password)\\s*=\\s*[\"'][^\"']+[\"']",
                "message": "hardcoded secret",
            }
        ],
    )
    scope = file_scope(repo, auth)
    with patch("scout.hawkeye.backends.resolve.discover_scout_for_setup", return_value=None):
        result = run_review(cfg, scope=scope, repo_root=repo, backend_mode="filesystem")

    assert result.backend == "filesystem"
    assert any(f.rule_id == "AP-HARDCODED-SECRET" for f in result.findings)
    session = json.loads(result.trace_path.read_text().splitlines()[0])
    assert session.get("backend") == "filesystem"


def test_auto_falls_back_to_filesystem(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    target = repo / "main.py"
    target.write_text("x = 1\n")
    cfg = HawkeyeConfig(
        scout_api="",
        default_space="local",
        config_dir=tmp_path / ".hawkeye",
        trace_dir=tmp_path / "traces",
        rules=[],
        antipatterns=[],
    )
    with (
        patch("scout.hawkeye.backends.resolve.discover_scout_for_setup", return_value=None),
        patch("scout.hawkeye.backends.resolve.probe_scout_health", return_value=False),
    ):
        result = run_review(cfg, scope=file_scope(repo, target), repo_root=repo, backend_mode="auto")
    assert result.backend == "filesystem"
    assert "filesystem backend" in capsys.readouterr().err


def test_graph_mode_requires_scout(tmp_path: Path) -> None:
    cfg = HawkeyeConfig(
        scout_api="",
        default_space="local",
        config_dir=tmp_path / ".hawkeye",
        trace_dir=tmp_path / "traces",
        rules=[],
        antipatterns=[],
    )
    with (
        patch("scout.hawkeye.backends.resolve.discover_scout_for_setup", return_value=None),
        patch("scout.hawkeye.backends.resolve.probe_scout_health", return_value=False),
    ):
        try:
            resolve_backend(
                "graph",
                cfg=cfg,
                repo_root=tmp_path,
                session_id="s1",
                trace=TraceStore(tmp_path / "traces", "s1"),
            )
        except RuntimeError as exc:
            assert "graph backend requires Scout" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_load_config_or_defaults_without_setup(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = tmp_path / "unused-global"
        cfg = load_config_or_defaults(tmp_path)
        assert cfg.default_space == "local"
        assert cfg.rules
        assert cfg.trace_dir == tmp_path / ".hawkeye" / "traces"
        assert cfg.trace_dir.is_dir()
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig
