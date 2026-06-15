"""Tests for unified setup wizard."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from scout.config import ScoutConfig, SpaceEntry, bootstrap_scout_dir, load_config, save_config
from scout.setup.api_url import (
    build_scout_api_url,
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


@pytest.mark.asyncio
async def test_run_setup_uses_selected_src_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index root follows source-folder picker; skill install stays at workspace anchor."""
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text("print('ok')\n", encoding="utf-8")
    scout_home = tmp_path / ".scout"
    monkeypatch.chdir(repo)
    monkeypatch.setattr("scout.setup.runner.bootstrap_scout_dir", lambda: scout_home)
    monkeypatch.setattr("scout.setup.runner.load_config", lambda home: ScoutConfig())
    monkeypatch.setattr("scout.setup.runner.save_config", lambda home, cfg: None)
    captured_entry: dict[str, SpaceEntry] = {}

    def capture_register(home, entry, cfg):
        captured_entry["entry"] = entry

    monkeypatch.setattr("scout.setup.runner.register_space", capture_register)
    monkeypatch.setattr(
        "scout.setup.runner.resolve_discovered_api_url",
        lambda cfg: None,
    )
    monkeypatch.setattr(
        "scout.setup.runner.prompt_api_base_url",
        lambda cfg, discovered=None: "http://127.0.0.1:8741/v1",
    )
    monkeypatch.setattr("scout.setup.runner.ensure_api_port_available", lambda cfg: None)
    monkeypatch.setattr(
        "scout.setup.runner.prompt_setup_branch",
        lambda: __import__("scout.setup.prompts", fromlist=["SetupBranch"]).SetupBranch.LOCAL,
    )
    monkeypatch.setattr("scout.setup.runner.resolve_local_root", lambda: repo.resolve())
    monkeypatch.setattr("scout.setup.runner.prompt_index_subdirectory", lambda anchor: src.resolve())
    monkeypatch.setattr(
        "scout.setup.runner.run_prescan",
        lambda root, globs, paths, **kwargs: MagicMock(total_bytes=1, file_count=1),
    )
    monkeypatch.setattr("scout.setup.runner.display_prescan_table", lambda *a, **k: None)
    monkeypatch.setattr("scout.setup.runner.check_byte_cap", lambda *a, **k: None)
    monkeypatch.setattr("scout.setup.runner.check_capacity", lambda *a, **k: None)
    monkeypatch.setattr("scout.setup.runner.write_prescan_json", lambda *a, **k: None)

    def confirm_side_effect(msg: str, default: bool = True) -> bool:
        if "embed provider" in msg.lower():
            return False
        return True

    monkeypatch.setattr("scout.setup.runner.typer.confirm", confirm_side_effect)
    monkeypatch.setattr(
        "scout.setup.runner.run_reindex",
        AsyncMock(return_value="graph-only:v1"),
    )
    monkeypatch.setattr("scout.setup.runner.prompt_agent", lambda override: "cursor")
    monkeypatch.setattr(
        "scout.setup.runner.prompt_skill_scope",
        lambda: (False, False),
    )

    captured: dict[str, object] = {}

    def capture_install(agent, **kwargs):
        captured["agent"] = agent
        captured.update(kwargs)
        return []

    monkeypatch.setattr("scout.setup.runner.install_skill", capture_install)

    from scout.setup.runner import run_setup

    await run_setup("demo")

    assert captured["project_root"] == repo.resolve()
    assert captured["default_space"] == "demo"
    assert captured_entry["entry"].root == str(src.resolve())


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
    assert SetupBranch.LOCAL.uses_git is False
    assert SetupBranch.GIT.uses_git is True


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
    monkeypatch.setattr(
        cli_main,
        "create_app",
        lambda embed_mode=False, warm_cache=True: MagicMock(),
    )

    cli_main.main(["serve"])

    assert captured["host"] == "192.168.1.10"
    assert captured["port"] == 8741
