"""Setup security and validation tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from scout.hawkeye.setup_cmd import _validate_scout_api_url, run_setup


def test_validate_scout_api_url_rejects_bad() -> None:
    with pytest.raises(ValueError, match="invalid scout_api"):
        _validate_scout_api_url("not-a-url")


def test_validate_scout_api_url_accepts_local_http() -> None:
    assert _validate_scout_api_url("http://127.0.0.1:8741/v1").startswith("http://")


def test_setup_refuses_overwrite_without_force(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    target = tmp_path / ".hawkeye"
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = target
        run_setup(
            scout_api="http://127.0.0.1:8741/v1",
            space="sp",
            force=True,
        )
        with pytest.raises(FileExistsError, match="use --force"):
            run_setup(
                scout_api="http://127.0.0.1:8741/v1",
                space="sp",
                force=False,
            )
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig


def test_setup_config_mode_600(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    target = tmp_path / ".hawkeye"
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = target
        run_setup(
            scout_api="http://127.0.0.1:8741/v1",
            space="sp",
            force=True,
        )
        mode = stat.S_IMODE((target / "config.yaml").stat().st_mode)
        assert mode == 0o600
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig


def test_setup_malformed_url(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    target = tmp_path / ".hawkeye"
    orig = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = target
        with pytest.raises(ValueError, match="invalid scout_api"):
            run_setup(scout_api="bad-url", space="sp", force=True)
        assert not (target / "config.yaml").exists()
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig
