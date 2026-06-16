"""Workspace path validation before scout_core calls.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import posixpath
from pathlib import Path
from urllib.parse import unquote


class PathSafetyError(ValueError):
    """Unsafe workspace-relative path."""


def validate_rel_path(space_root: str | Path, rel_path: str) -> str:
    """Return normalized rel_path or raise PathSafetyError."""
    if not rel_path or not rel_path.strip():
        raise PathSafetyError("rel_path is required")
    if "\0" in rel_path:
        raise PathSafetyError("invalid path")

    decoded = unquote(rel_path.replace("\\", "/"))
    normalized = posixpath.normpath(decoded)
    if normalized in {".", ""}:
        raise PathSafetyError("invalid path")
    if normalized.startswith("/"):
        raise PathSafetyError("invalid path")
    if normalized == ".." or normalized.startswith("../"):
        raise PathSafetyError("path traversal not allowed")

    parts = normalized.split("/")
    if ".." in parts:
        raise PathSafetyError("path traversal not allowed")

    root = Path(space_root).expanduser().resolve()
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError("path outside space root") from exc
    return normalized


def rel_path_matches_prefix(rel_path: str, path_prefix: str) -> bool:
    """True when rel_path is under path_prefix (segment-safe).

    Trailing slash on prefix means children only (exclude exact directory node).
    """
    if not path_prefix:
        return bool(rel_path)
    raw = path_prefix.strip().replace("\\", "/")
    if not raw:
        return True
    children_only = raw.endswith("/")
    prefix = posixpath.normpath(raw)
    if not prefix or prefix == ".":
        return True
    if rel_path == prefix:
        return not children_only
    return rel_path.startswith(f"{prefix}/")


def validate_path_prefix(path_prefix: str | None) -> str:
    """Validate optional path_prefix query/filter value."""
    if path_prefix is None:
        return ""
    value = path_prefix.strip()
    if not value:
        return ""
    if "\0" in value:
        raise PathSafetyError("invalid path_prefix")
    decoded = unquote(value.replace("\\", "/"))
    children_only = decoded.endswith("/")
    normalized = posixpath.normpath(decoded)
    if normalized.startswith("/"):
        raise PathSafetyError("invalid path_prefix")
    if ".." in normalized.split("/"):
        raise PathSafetyError("invalid path_prefix")
    if not normalized or normalized == ".":
        return ""
    if children_only:
        return f"{normalized}/"
    return normalized
