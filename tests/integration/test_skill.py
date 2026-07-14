"""Agent skill install tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scout.skill.install import AGENT_PATHS, install_skill


def test_skill_install_project_cursor(tmp_path: Path) -> None:
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
            scout_api="http://127.0.0.1:8741/v1",
            default_space="test",
            force=True,
        )
    assert len(dests) == 3
    dest_names = {d.name for d in dests}
    assert dest_names == {"search_scout", "add_memory", "ask_scout"}
    for dest in dests:
        content = dest.joinpath("SKILL.md").read_text(encoding="utf-8")
        assert "http://127.0.0.1:8741/v1" in content
        assert "test" in content


def test_skill_install_project_pi_uses_hyphen_name(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "---\nname: search-scout\ndescription: test\n---\n"
            "api={{SCOUT_API}} space={{DEFAULT_SPACE}}",
            encoding="utf-8",
        )
        mock_tpl.return_value = tpl
        dests = install_skill(
            "pi",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="test",
            force=True,
        )
    dest_names = {d.name for d in dests}
    assert dest_names == {"search-scout", "add-memory", "ask-scout"}
    # Verify pi hyphen naming preserved
    for dest in dests:
        content = dest.joinpath("SKILL.md").read_text(encoding="utf-8")
        if "search-scout" in content:
            assert "name: search-scout" in content


def test_skill_install_global_custom_api_url(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "scout_api: {{SCOUT_API}}\ndefault_space: {{DEFAULT_SPACE}}",
            encoding="utf-8",
        )
        mock_tpl.return_value = tpl
        dests = install_skill(
            "cursor",
            global_install=True,
            project_install=False,
            project_root=project,
            scout_api="http://10.0.0.5:9000/v1",
            default_space="remote",
            force=True,
        )
    assert len(dests) == 3
    for dest in dests:
        content = dest.joinpath("SKILL.md").read_text(encoding="utf-8")
        assert "http://10.0.0.5:9000/v1" in content
        assert "remote" in content


def test_install_skill_installs_both_templates(tmp_path: Path) -> None:
    """install_skill() returns paths for search, memory, and ask skills."""
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
            "opencode",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://127.0.0.1:8741/v1",
            default_space="test",
            force=True,
        )
    assert len(dests) == 3
    dest_names = {d.name for d in dests}
    assert dest_names == {"search_scout", "add_memory", "ask_scout"}


def test_placeholder_injection_works_for_both_skills(tmp_path: Path) -> None:
    """Placeholder injection replaces {{SCOUT_API}} and {{DEFAULT_SPACE}} in both skills."""
    project = tmp_path / "proj"
    project.mkdir()
    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text(
            "api={{SCOUT_API}} space={{DEFAULT_SPACE}} name={{SKILL_NAME}}",
            encoding="utf-8",
        )
        mock_tpl.return_value = tpl
        dests = install_skill(
            "cursor",
            global_install=False,
            project_install=True,
            project_root=project,
            scout_api="http://custom:1234/v1",
            default_space="myapp",
            force=True,
        )
    for dest in dests:
        content = dest.joinpath("SKILL.md").read_text(encoding="utf-8")
        assert "http://custom:1234/v1" in content
        assert "myapp" in content
        # Placeholders should be fully replaced
        assert "{{SCOUT_API}}" not in content
        assert "{{DEFAULT_SPACE}}" not in content


def test_file_exists_error_when_either_skill_already_exists(tmp_path: Path) -> None:
    """FileExistsError raised when one of the skill directories already exists."""
    project = tmp_path / "proj"
    project.mkdir()
    # Pre-create the first skill directory
    first_dest = project / ".cursor" / "skills" / "search_scout"
    first_dest.mkdir(parents=True)
    (first_dest / "SKILL.md").write_text("existing", encoding="utf-8")

    with patch("scout.skill.install.skill_template_path") as mock_tpl:
        tpl = tmp_path / "template"
        tpl.mkdir()
        (tpl / "SKILL.md").write_text("test", encoding="utf-8")
        mock_tpl.return_value = tpl

        with pytest.raises(FileExistsError) as exc_info:
            install_skill(
                "cursor",
                global_install=False,
                project_install=True,
                project_root=project,
                scout_api="http://127.0.0.1:8741/v1",
                default_space="test",
                force=False,
            )
    assert "search_scout" in str(exc_info.value)
    assert "use --force" in str(exc_info.value)


def test_agent_paths_include_ask_scout(tmp_path: Path) -> None:
    """AGENT_PATHS has search, memory, and ask entries for all agents."""
    for agent_name, skills in AGENT_PATHS.items():
        skill_names = [s["name"] for s in skills]
        assert "search_scout" in skill_names or "search-scout" in skill_names
        assert "add_memory" in skill_names or "add-memory" in skill_names
        assert "ask_scout" in skill_names or "ask-scout" in skill_names
        assert len(skills) == 3
