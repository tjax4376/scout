"""Tests for workspace path validation."""

from __future__ import annotations

import pytest

from scout.api.path_safety import PathSafetyError, validate_path_prefix, validate_rel_path


def test_validate_rel_path_accepts_normal_file(tmp_path) -> None:
    rel = validate_rel_path(tmp_path, "src/main.py")
    assert rel == "src/main.py"


def test_validate_rel_path_rejects_traversal(tmp_path) -> None:
    with pytest.raises(PathSafetyError, match="traversal"):
        validate_rel_path(tmp_path, "../outside.py")


def test_validate_rel_path_rejects_url_encoded_traversal(tmp_path) -> None:
    with pytest.raises(PathSafetyError, match="traversal"):
        validate_rel_path(tmp_path, "%2e%2e/outside.py")


def test_validate_rel_path_rejects_absolute(tmp_path) -> None:
    with pytest.raises(PathSafetyError, match="invalid path"):
        validate_rel_path(tmp_path, "/etc/passwd")


def test_validate_rel_path_rejects_null_byte(tmp_path) -> None:
    with pytest.raises(PathSafetyError, match="invalid path"):
        validate_rel_path(tmp_path, "a\x00b")


def test_validate_path_prefix_rejects_traversal() -> None:
    with pytest.raises(PathSafetyError, match="path_prefix"):
        validate_path_prefix("../../etc")
