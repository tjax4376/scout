"""scout_api.py URL resolution tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "search_scout" / "scripts" / "scout_api.py"
_spec = importlib.util.spec_from_file_location("scout_api", _SCRIPT)
assert _spec and _spec.loader
scout_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scout_api)

SKILL_MD = Path(__file__).resolve().parents[2] / "skills" / "search_scout" / "SKILL.md"


def test_normalize_base_url_adds_v1_suffix() -> None:
    assert scout_api.normalize_base_url("http://127.0.0.1:8747") == "http://127.0.0.1:8747/v1"


def test_normalize_base_url_strips_trailing_slash() -> None:
    assert scout_api.normalize_base_url("http://127.0.0.1:8747/v1/") == "http://127.0.0.1:8747/v1"


def test_resolve_api_path_avoids_duplicate_v1() -> None:
    base = "http://127.0.0.1:8747/v1"
    assert scout_api.resolve_api_path(base, "/health") == "http://127.0.0.1:8747/v1/health"
    assert scout_api.resolve_api_path(base, "/v1/health") == "http://127.0.0.1:8747/v1/health"


def test_config_defaults_to_8747(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCOUT_API_URL", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    base_url, token = scout_api._config()
    assert base_url == "http://127.0.0.1:8747/v1"
    assert token == ""


def test_config_prefers_env_over_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCOUT_API_URL", "http://127.0.0.1:9000/v1")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    base_url, _ = scout_api._config()
    assert base_url == "http://127.0.0.1:9000/v1"


def test_config_prefers_yaml_over_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCOUT_API_URL", raising=False)
    fake_home = tmp_path / "home"
    scout_dir = fake_home / ".scout"
    scout_dir.mkdir(parents=True)
    (scout_dir / "config.yaml").write_text(
        "api_base_url: http://127.0.0.1:8741/v1\n", encoding="utf-8"
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    base_url, _ = scout_api._config()
    assert base_url == "http://127.0.0.1:8741/v1"


def test_health_uses_single_v1_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_request(method: str, url: str, body: str | None, token: str) -> int:
        captured["url"] = url
        return 0

    monkeypatch.setattr(scout_api, "_config", lambda: ("http://127.0.0.1:8747/v1", ""))
    monkeypatch.setattr(scout_api, "_request", fake_request)

    with patch.object(scout_api.sys, "argv", ["scout_api.py", "health"]):
        assert scout_api.main() == 0
    assert captured["url"] == "http://127.0.0.1:8747/v1/health"


def test_skill_documents_port_8747_default() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "8747" in content
    assert "Default API" in content
