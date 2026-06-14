"""Tests for scout stop-serve."""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import pytest

from scout.serve.lifecycle import stop_serve


def test_stop_serve_missing_pid(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    result = stop_serve(home)
    assert result.status == "not_running"
    assert "not running" in result.message.lower()


def test_stop_serve_stale_pid(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    pid_file = home / "scout.pid"
    pid_file.write_text("999999", encoding="utf-8")
    result = stop_serve(home)
    assert result.status == "stale_removed"
    assert not pid_file.exists()


def test_stop_serve_invalid_pid_file(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    pid_file = home / "scout.pid"
    pid_file.write_text("not-a-pid", encoding="utf-8")
    result = stop_serve(home)
    assert result.status == "stale_removed"
    assert not pid_file.exists()


def test_stop_serve_stops_running_process(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    pid_file = home / "scout.pid"
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    try:
        result = stop_serve(home)
        assert result.status == "stopped"
        assert result.pid == proc.pid
        assert not pid_file.exists()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_stop_serve_sigkill_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    pid_file = home / "scout.pid"
    pid_file.write_text("4242", encoding="utf-8")

    alive = {"value": True}

    def fake_alive(pid: int) -> bool:
        return alive["value"]

    def fake_kill(pid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            alive["value"] = False

    monkeypatch.setattr("scout.serve.lifecycle._process_alive", fake_alive)
    monkeypatch.setattr("scout.serve.lifecycle.os.kill", fake_kill)
    monkeypatch.setattr("scout.serve.lifecycle.TERMINATE_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr("scout.serve.lifecycle.KILL_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr("scout.serve.lifecycle.POLL_INTERVAL_SECS", 0.01)

    result = stop_serve(home)
    assert result.status == "stopped"
    assert not pid_file.exists()


def test_stop_serve_fails_after_sigkill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    pid_file = home / "scout.pid"
    pid_file.write_text("4343", encoding="utf-8")

    monkeypatch.setattr("scout.serve.lifecycle._process_alive", lambda pid: True)
    monkeypatch.setattr("scout.serve.lifecycle.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("scout.serve.lifecycle._wait_for_exit", lambda pid, timeout: False)

    result = stop_serve(home)
    assert result.status == "failed"
    assert pid_file.exists()


def test_cli_stop_serve_invokes_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scout.cli.main as cli_main
    from scout.serve.lifecycle import StopServeResult

    captured: dict[str, Path] = {}

    def fake_stop(home: Path) -> StopServeResult:
        captured["home"] = home
        return StopServeResult("not_running", "scout serve is not running")

    monkeypatch.setattr(cli_main, "scout_home", lambda: tmp_path / ".scout")
    monkeypatch.setattr(cli_main, "stop_serve", fake_stop)

    cli_main.main(["stop-serve"])
    assert captured["home"] == tmp_path / ".scout"


def test_cli_stop_serve_exit_code_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scout.cli.main as cli_main
    from scout.serve.lifecycle import StopServeResult

    monkeypatch.setattr(cli_main, "scout_home", lambda: tmp_path / ".scout")
    monkeypatch.setattr(
        cli_main,
        "stop_serve",
        lambda home: StopServeResult("failed", "failed to stop"),
    )

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["stop-serve"])
    assert exc.value.code == 1
