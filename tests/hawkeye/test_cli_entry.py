"""Hawkeye CLI entry smoke tests."""

from __future__ import annotations

import subprocess
import sys

from scout.hawkeye.cli.main import main


def test_hawkeye_main_help() -> None:
    with __import__("pytest").raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_hawkeye_module_help_matches() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "scout.hawkeye", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "setup" in proc.stdout
    assert "review" in proc.stdout
