"""Tests for graceful CLI error handling."""

from __future__ import annotations

import pytest

from scout.cli.errors import FAREWELL
from scout.config import SpaceEntry, load_config, save_config


def _patch_cli_home(monkeypatch: pytest.MonkeyPatch, home) -> None:
    import scout.cli.main as cli_main

    monkeypatch.setattr(cli_main, "scout_home", lambda: home)
    monkeypatch.setattr(cli_main, "_home", lambda: home)


def test_unknown_space_no_traceback(
    patch_scout_config_home,
    sample_project,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.cli.main as cli_main

    home = patch_scout_config_home
    config = load_config(home)
    config.spaces["scout"] = SpaceEntry(name="scout", root=str(sample_project))
    save_config(home, config)
    _patch_cli_home(monkeypatch, home)
    monkeypatch.setattr(cli_main, "_require_core", lambda: None)

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["scour", "search", "auth"])

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Unknown space: scour" in err
    assert "Configured spaces: scout" in err
    assert "Run: scout <space> setup" in err
    assert FAREWELL in err
    assert "Traceback" not in err


def test_unknown_space_lists_configured_spaces(
    patch_scout_config_home,
    sample_project,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.cli.main as cli_main

    home = patch_scout_config_home
    config = load_config(home)
    config.spaces["alpha"] = SpaceEntry(name="alpha", root=str(sample_project))
    config.spaces["beta"] = SpaceEntry(name="beta", root=str(sample_project))
    save_config(home, config)
    _patch_cli_home(monkeypatch, home)
    monkeypatch.setattr(cli_main, "_require_core", lambda: None)

    with pytest.raises(SystemExit):
        cli_main.main(["nope", "search", "q"])

    err = capsys.readouterr().err
    assert "Configured spaces: alpha, beta" in err


def test_missing_graph_index(
    patch_scout_config_home,
    sample_project,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.cli.main as cli_main

    home = patch_scout_config_home
    config = load_config(home)
    config.spaces["myapp"] = SpaceEntry(name="myapp", root=str(sample_project))
    save_config(home, config)
    _patch_cli_home(monkeypatch, home)
    monkeypatch.setattr(cli_main, "_require_core", lambda: None)

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["myapp", "search", "auth"])

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "graph index not found" in err
    assert FAREWELL in err
    assert "Traceback" not in err


def test_debug_mode_shows_traceback(
    patch_scout_config_home,
    sample_project,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    import scout.cli.main as cli_main

    home = patch_scout_config_home
    config = load_config(home)
    config.spaces["myapp"] = SpaceEntry(name="myapp", root=str(sample_project))
    save_config(home, config)
    _patch_cli_home(monkeypatch, home)
    monkeypatch.setattr(cli_main, "_require_core", lambda: None)
    monkeypatch.setenv("SCOUT_DEBUG", "1")

    mock_core = MagicMock()
    mock_core.py_index_exists.return_value = True
    monkeypatch.setattr(cli_main, "scout_core", mock_core)

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(cli_main, "validate_embed", boom)

    with pytest.raises(SystemExit):
        cli_main.main(["myapp", "search", "auth"])

    err = capsys.readouterr().err
    assert "Traceback" in err
    assert "unexpected boom" in err
    assert FAREWELL in err


def test_help_exits_without_farewell(capsys) -> None:
    import scout.cli.main as cli_main

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["--help"])

    assert exc.value.code == 0
    err = capsys.readouterr().err
    assert FAREWELL not in err


def test_stop_serve_not_running_no_farewell(
    patch_scout_config_home,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.cli.main as cli_main

    _patch_cli_home(monkeypatch, patch_scout_config_home)

    cli_main.main(["stop-serve"])

    err = capsys.readouterr().err
    assert FAREWELL not in err


def test_corrupt_config_yaml(
    patch_scout_config_home,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scout.cli.main as cli_main

    home = patch_scout_config_home
    (home / "config.yaml").write_text("spaces: [invalid", encoding="utf-8")
    _patch_cli_home(monkeypatch, home)
    monkeypatch.setattr(cli_main, "bootstrap_scout_dir", lambda: home)
    monkeypatch.setattr(cli_main, "_require_core", lambda: None)

    with pytest.raises(SystemExit):
        cli_main.main(["serve"])

    err = capsys.readouterr().err
    assert "Could not read Scout config" in err
    assert FAREWELL in err
    assert "Traceback" not in err
