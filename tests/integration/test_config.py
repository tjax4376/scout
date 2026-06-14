"""Config bootstrap tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import bootstrap_scout_dir


def test_config_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    assert (home / "config.yaml").exists()
    assert (home / "secrets.yaml").exists()
