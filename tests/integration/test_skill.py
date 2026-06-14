"""Agent skill install tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scout.skill.install import install_skill


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
    assert len(dests) == 1
    assert dests[0].name == "search_scout"
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
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
    assert dests[0].name == "search-scout"
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
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
    content = dests[0].joinpath("SKILL.md").read_text(encoding="utf-8")
    assert "http://10.0.0.5:9000/v1" in content
    assert "remote" in content
