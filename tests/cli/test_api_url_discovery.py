"""API URL discovery tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scout.config import ScoutConfig
from scout.setup.api_url import (
    discover_scout_api_url,
    ensure_api_port_available,
    probe_scout_health,
    resolve_discovered_api_url,
)


def test_probe_scout_health_ok() -> None:
    with patch("scout.setup.api_url.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value.status_code = 200
        client.get.return_value.json.return_value = {"status": "ok"}
        assert probe_scout_health("http://127.0.0.1:8747/v1") is True


def test_probe_scout_health_rejects_non_scout() -> None:
    with patch("scout.setup.api_url.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value.status_code = 200
        client.get.return_value.json.return_value = {"status": "up"}
        assert probe_scout_health("http://127.0.0.1:8747/v1") is False


def test_discover_scout_api_url_scans_ports() -> None:
    with patch("scout.setup.api_url._port_open", side_effect=lambda _h, p: p == 8747):
        with patch(
            "scout.setup.api_url.probe_scout_health",
            side_effect=lambda url: "8747" in url,
        ):
            assert discover_scout_api_url() == "http://127.0.0.1:8747/v1"


def test_resolve_discovered_prefers_config_when_healthy() -> None:
    config = ScoutConfig(api_base_url="http://127.0.0.1:8747/v1", api_port=8747)
    with patch("scout.setup.api_url.probe_scout_health", return_value=True):
        assert resolve_discovered_api_url(config) == "http://127.0.0.1:8747/v1"


def test_ensure_api_port_keeps_scout_serving_port() -> None:
    config = ScoutConfig(api_base_url="http://127.0.0.1:8747/v1", api_port=8747)
    with patch("scout.setup.api_url._port_open", return_value=True):
        with patch("scout.setup.api_url.probe_scout_health", return_value=True):
            ensure_api_port_available(config)
    assert config.api_port == 8747
    assert config.api_base_url == "http://127.0.0.1:8747/v1"


def test_ensure_api_port_bumps_when_non_scout_occupies_port() -> None:
    config = ScoutConfig(api_base_url="http://127.0.0.1:8741/v1", api_port=8741)
    with patch("scout.setup.api_url._port_open", return_value=True):
        with patch("scout.setup.api_url.probe_scout_health", return_value=False):
            with patch(
                "scout.setup.api_url.find_free_api_port_on_host",
                return_value=8742,
            ):
                ensure_api_port_available(config)
    assert config.api_port == 8742
    assert config.api_base_url == "http://127.0.0.1:8742/v1"
