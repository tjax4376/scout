"""Skill template content tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "code-reviewer-scout"


def test_skill_directory_has_required_files() -> None:
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "README.md").is_file()
    assert (SKILL_ROOT / "scripts" / "review_api.py").is_file()


def test_skill_name_uses_hyphens_only() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: code-reviewer-scout" in content
    assert "name: code_reviewer_scout" not in content


def test_skill_documents_escalation_ladder() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "Review escalation ladder" in content
    assert "Scope" in content
    assert "Search" in content
    assert "Expand" in content
    assert "Full read" in content
    assert "in-memory" in content.lower()


def test_skill_references_rest_endpoints() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "/search" in content
    assert "/node/" in content
    assert "/spaces/list" in content
    assert "/health" in content


def test_skill_has_config_placeholders() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "{{SCOUT_API}}" in content
    assert "{{DEFAULT_SPACE}}" in content
