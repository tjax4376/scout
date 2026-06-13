"""Tests for unified setup wizard."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.config import ScoutConfig, bootstrap_scout_dir, load_config, save_config
from scout.setup.api_url import (
    build_scout_api_url,
    migrate_api_base_url,
    normalize_api_base_url,
    parse_api_base_url,
    repo_name_from_url,
    update_api_base_url_port,
    validate_git_url,
    validate_subdir_name,
)
from scout.setup.prompts import (
    SetupBranch,
    prompt_agent,
    prompt_local_api_key,
    prompt_openrouter_api_key,
)
from scout.setup.workspace import clone_git_workspace


def test_normalize_api_base_url() -> None:
    assert normalize_api_base_url("http://127.0.0.1:8741/v1") == "http://127.0.0.1:8741/v1"
    assert normalize_api_base_url("http://10.0.0.5:9000/v1/") == "http://10.0.0.5:9000/v1"


def test_normalize_api_base_url_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="scheme"):
        normalize_api_base_url("ftp://127.0.0.1:8741/v1")
    with pytest.raises(ValueError, match="port"):
        normalize_api_base_url("http://127.0.0.1/v1")
    with pytest.raises(ValueError, match="/v1"):
        normalize_api_base_url("http://127.0.0.1:8741")


def test_parse_api_base_url() -> None:
    ep = parse_api_base_url("http://192.168.1.10:8741/v1")
    assert ep.host == "192.168.1.10"
    assert ep.port == 8741
    assert ep.scheme == "http"


def test_build_scout_api_url_from_config() -> None:
    config = ScoutConfig(api_base_url="http://10.0.0.5:9000/v1", api_port=9000)
    assert build_scout_api_url(config) == "http://10.0.0.5:9000/v1"


def test_config_migration_api_port_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    config = ScoutConfig(api_port=8742, api_base_url="")
    save_config(home, config)
    loaded = load_config(home)
    assert loaded.api_base_url == "http://127.0.0.1:8742/v1"


def test_update_api_base_url_port() -> None:
    config = ScoutConfig(api_base_url="http://10.0.0.5:8741/v1", api_port=8741)
    update_api_base_url_port(config, 8745)
    assert config.api_port == 8745
    assert config.api_base_url == "http://10.0.0.5:8745/v1"


def test_setup_branch_flags() -> None:
    assert SetupBranch.LOCAL_LOCAL.uses_git is False
    assert SetupBranch.LOCAL_REMOTE.uses_openrouter is True
    assert SetupBranch.GIT_LOCAL.uses_git is True
    assert SetupBranch.GIT_REMOTE.uses_openrouter is True


def test_validate_git_url() -> None:
    assert validate_git_url("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    assert validate_git_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"
    with pytest.raises(ValueError):
        validate_git_url("not-a-url")


def test_validate_subdir_name() -> None:
    assert validate_subdir_name("myrepo") == "myrepo"
    with pytest.raises(ValueError):
        validate_subdir_name("../escape")
    with pytest.raises(ValueError):
        validate_subdir_name("bad;name")


def test_repo_name_from_url() -> None:
    assert repo_name_from_url("https://github.com/org/my-app.git") == "my-app"
    assert repo_name_from_url("git@github.com:org/foo.git") == "foo"


def test_prompt_openrouter_blank_keeps_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ScoutConfig()
    config.embed.provider = "openrouter"
    config.embed.model = "text-embed"
    secrets = {"openrouter_api_key": "sk-existing"}
    monkeypatch.setattr("scout.setup.prompts.typer.prompt", lambda *a, **k: "")
    assert prompt_openrouter_api_key(secrets, config) == "sk-existing"


def test_prompt_local_blank_keeps_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ScoutConfig()
    config.embed.provider = "lmstudio"
    config.embed.model = "embed-model"
    secrets = {"lmstudio_api_key": "local-key"}
    monkeypatch.setattr("scout.setup.prompts.typer.prompt", lambda *a, **k: "")
    assert prompt_local_api_key("lmstudio", secrets, config) == "local-key"


def test_prompt_agent_override() -> None:
    assert prompt_agent("cursor") == "cursor"


def test_clone_git_workspace_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "repo"
    target.mkdir()

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        (Path(cmd[-1]) / ".git").mkdir()
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("scout.setup.workspace.subprocess.run", fake_run)
    result = clone_git_workspace(
        cwd=tmp_path,
        git_url="https://github.com/org/repo.git",
        subdir="repo",
    )
    assert result == target.resolve()


def test_clone_git_workspace_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "clone failed")

    monkeypatch.setattr("scout.setup.workspace.subprocess.run", fake_run)
    with pytest.raises(SystemExit):
        clone_git_workspace(
            cwd=tmp_path,
            git_url="https://github.com/org/repo.git",
            subdir="repo",
        )


def test_skill_install_custom_api_url(tmp_path: Path) -> None:
    from scout.skill.install import install_skill

    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "api={{SCOUT_API}} space={{DEFAULT_SPACE}}", encoding="utf-8"
        )
        mock_tpl.return_value = tpl
        dests = install_skill(
            "cursor",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://10.0.0.5:9000/v1",
            default_space="myspace",
            force=True,
        )
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
    assert "http://10.0.0.5:9000/v1" in content
    assert "myspace" in content


def test_serve_uses_parsed_host(monkeypatch: pytest.MonkeyPatch) -> None:
    import scout.cli.main as cli_main

    config = ScoutConfig(api_base_url="http://192.168.1.10:8741/v1", api_port=8741)
    monkeypatch.setattr(cli_main, "bootstrap_scout_dir", lambda: Path("/tmp/.scout"))
    monkeypatch.setattr(cli_main, "load_config", lambda home: config)
    monkeypatch.setattr(cli_main, "pid_path", lambda home: Path("/tmp/.scout/scout.pid"))
    pid_file = Path("/tmp/.scout/scout.pid")
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    if pid_file.exists():
        pid_file.unlink()

    captured: dict = {}

    def fake_uvicorn(app, host, port, log_level):
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(cli_main.uvicorn, "run", fake_uvicorn)
    monkeypatch.setattr(cli_main, "create_app", lambda: MagicMock())

    cli_main.main(["serve"])

    assert captured["host"] == "192.168.1.10"
    assert captured["port"] == 8741
