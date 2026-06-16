"""Tests for HTTPS transport defaults in Scout config."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import (
    ScoutConfig,
    bootstrap_scout_dir,
    default_api_base_url,
    is_loopback_host,
    load_config,
    save_config,
)
from scout.setup.api_url import migrate_api_base_url, normalize_api_base_url


def test_is_loopback_host() -> None:
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("192.168.1.10") is False


def test_default_api_base_url_loopback_http() -> None:
    assert default_api_base_url(8741) == "http://127.0.0.1:8741/v1"


def test_default_api_base_url_lan_https() -> None:
    assert default_api_base_url(8741, "192.168.1.10") == "https://192.168.1.10:8741/v1"


def test_normalize_api_base_url_upgrades_lan_http() -> None:
    assert normalize_api_base_url("http://10.0.0.5:9000/v1/") == "https://10.0.0.5:9000/v1"


def test_load_config_loopback_default_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    save_config(home, ScoutConfig(api_port=8742, api_base_url=""))
    loaded = load_config(home)
    assert loaded.api_base_url == "http://127.0.0.1:8742/v1"
    assert loaded.api.force_https is False


def test_load_config_lan_http_upgrades_to_https(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    save_config(
        home,
        ScoutConfig(api_port=8741, api_base_url="http://192.168.1.10:8741/v1"),
    )
    loaded = load_config(home)
    assert loaded.api_base_url == "https://192.168.1.10:8741/v1"
    assert loaded.api.force_https is True


def test_migrate_api_base_url_uses_loopback_default() -> None:
    config = ScoutConfig(api_port=8743, api_base_url="")
    migrate_api_base_url(config)
    assert config.api_base_url == "http://127.0.0.1:8743/v1"
