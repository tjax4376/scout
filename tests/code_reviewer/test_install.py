"""Install tests for code-reviewer-scout skill."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scout.code_reviewer import install as install_mod
from scout.code_reviewer.install import SKILL_DIR_NAME, install_code_reviewer_skill


def _cursor_project_path(root: Path) -> Path:
    return root / "agent-skills" / SKILL_DIR_NAME


@pytest.fixture
def patched_cursor_paths() -> dict:
    paths = {
        "cursor": {
            "global": Path("/tmp/unused-global-code-reviewer-scout"),
            "project": _cursor_project_path,
        },
    }
    with patch.object(install_mod, "AGENT_PATHS", paths):
        yield paths


def test_install_project_cursor_injects_config(
    tmp_path: Path, patched_cursor_paths: dict
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.code_reviewer.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "api={{SCOUT_API}} space={{DEFAULT_SPACE}}",
            encoding="utf-8",
        )
        mock_tpl.return_value = tpl
        dests = install_code_reviewer_skill(
            "cursor",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="myapp",
            force=True,
        )
    assert len(dests) == 1
    assert dests[0].name == SKILL_DIR_NAME
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
    assert "http://127.0.0.1:8741/v1" in content
    assert "myapp" in content


def test_install_all_agents_use_hyphen_dir_name() -> None:
    from scout.code_reviewer.install import AGENT_PATHS

    for agent, paths in AGENT_PATHS.items():
        assert paths["global"].name == SKILL_DIR_NAME
        project = paths["project"](Path("/proj"))
        assert project.name == SKILL_DIR_NAME
        assert "_" not in project.name, f"{agent} must not use underscores in skill dir"


def test_install_refuses_overwrite_without_force(
    tmp_path: Path, patched_cursor_paths: dict
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    dest = _cursor_project_path(project)
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("existing", encoding="utf-8")

    with patch("scout.code_reviewer.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text("new={{SCOUT_API}}", encoding="utf-8")
        mock_tpl.return_value = tpl
        with pytest.raises(FileExistsError, match="skill exists"):
            install_code_reviewer_skill(
                "cursor",
                global_install=False,
                project_install=True,
                project_root=project,
                scout_api="http://127.0.0.1:8741/v1",
                default_space="x",
                force=False,
            )


def test_install_force_replaces_existing(
    tmp_path: Path, patched_cursor_paths: dict
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    dest = _cursor_project_path(project)
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old", encoding="utf-8")

    with patch("scout.code_reviewer.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text("api={{SCOUT_API}}", encoding="utf-8")
        mock_tpl.return_value = tpl
        install_code_reviewer_skill(
            "cursor",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="new",
            force=True,
        )
    content = dest.joinpath("SKILL.md").read_text(encoding="utf-8")
    assert "old" not in content
    assert "8741" in content


def test_install_requires_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one"):
        install_code_reviewer_skill(
            "cursor",
            global_install=False,
            project_install=False,
            project_root=tmp_path,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="x",
        )
