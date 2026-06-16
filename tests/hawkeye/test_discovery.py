"""Scout discovery tests for Hawkeye setup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scout.hawkeye.discovery import (
    discover_scout_for_setup,
    fetch_scout_spaces,
    prepare_setup,
    resolve_setup_space,
)


def test_discover_scout_override_unhealthy() -> None:
    with patch("scout.hawkeye.discovery.probe_scout_health", return_value=False):
        with pytest.raises(ValueError, match="not healthy"):
            discover_scout_for_setup(None, scout_api_override="http://127.0.0.1:8741/v1")


def test_discover_scout_port_scan() -> None:
    with patch("scout.hawkeye.discovery._read_scout_api_from_config", return_value=None):
        with patch("scout.hawkeye.discovery.discover_scout_api_url", return_value="http://127.0.0.1:8741/v1"):
            assert discover_scout_for_setup(None) == "http://127.0.0.1:8741/v1"


def test_fetch_scout_spaces() -> None:
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"spaces": [{"name": "myapp"}, {"name": "other"}]}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, params=None):
            return FakeResp()

    with patch("scout.hawkeye.discovery.httpx.Client", FakeClient):
        assert fetch_scout_spaces("http://127.0.0.1:8741/v1") == ["myapp", "other"]


def test_resolve_setup_space_single() -> None:
    assert resolve_setup_space(["only"], None, yes_flag=False) == "only"


def test_resolve_setup_space_invalid_flag() -> None:
    with pytest.raises(ValueError, match="not in Scout config"):
        resolve_setup_space(["a", "b"], "missing", yes_flag=True)


def test_resolve_setup_space_multi_requires_flag_with_yes() -> None:
    with pytest.raises(ValueError, match="multiple Scout spaces"):
        resolve_setup_space(["a", "b"], None, yes_flag=True)


def test_prepare_setup_not_found() -> None:
    with patch("scout.hawkeye.discovery.discover_scout_for_setup", return_value=None):
        with pytest.raises(ValueError, match="Scout API not found"):
            prepare_setup(
                scout_api=None,
                space=None,
                project=False,
                project_root=Path("."),
                yes=True,
            )


def test_prepare_setup_manual_override(tmp_path: Path) -> None:
    with patch("scout.hawkeye.discovery.discover_scout_for_setup", return_value="http://127.0.0.1:8741/v1"):
        with patch("scout.hawkeye.discovery.fetch_scout_spaces", return_value=["myapp"]):
            with patch("scout.hawkeye.discovery.validate_space_exists"):
                api, space = prepare_setup(
                    scout_api="http://127.0.0.1:8741/v1",
                    space="myapp",
                    project=False,
                    project_root=tmp_path,
                    yes=True,
                )
    assert api == "http://127.0.0.1:8741/v1"
    assert space == "myapp"


def test_validate_space_exists_rejects_unknown_space() -> None:
    from scout.hawkeye.discovery import validate_space_exists

    with pytest.raises(ValueError, match="not in Scout config"):
        validate_space_exists("http://127.0.0.1:8751/v1", "missing", ["scout", "myapp"])


def test_validate_space_exists_accepts_listed_space() -> None:
    from scout.hawkeye.discovery import validate_space_exists

    validate_space_exists("http://127.0.0.1:8751/v1", "scout", ["scout", "myapp"])
