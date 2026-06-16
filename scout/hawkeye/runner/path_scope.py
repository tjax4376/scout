"""Path and directory review scope for Hawkeye.

Metadata: v1.2.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from scout.hawkeye.runner.diff_scope import derive_path_prefixes

SKIP_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".hawkeye", ".scout", ".venv", "venv"})
REVIEWABLE_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".rs",
        ".go",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".kt",
        ".swift",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".sql",
        ".yaml",
        ".yml",
        ".toml",
        ".md",
    }
)


@dataclass
class PathScope:
    """Review scope from explicit file or directory paths."""

    scope_ref: str
    changed_paths: list[str] = field(default_factory=list)
    changed_lines: dict[str, set[int]] = field(default_factory=dict)
    path_prefixes: list[str] = field(default_factory=list)


def _rel_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _lines_for_file(path: Path) -> set[int]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"cannot read file: {path}: {exc}") from exc
    count = max(1, text.count("\n") + (0 if text.endswith("\n") or not text else 1))
    return set(range(1, count + 1))


def _is_reviewable_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in REVIEWABLE_SUFFIXES


def file_scope(repo_root: Path, file_path: Path) -> PathScope:
    """Build whole-file review scope for one path."""
    root = repo_root.resolve()
    target = file_path if file_path.is_absolute() else root / file_path
    if not target.is_file():
        raise ValueError(f"file not found: {file_path}")
    rel = _rel_path(root, target)
    lines = _lines_for_file(target)
    scope = PathScope(scope_ref=f"file:{rel}", changed_paths=[rel], changed_lines={rel: lines})
    scope.path_prefixes = derive_path_prefixes(scope.changed_paths)
    return scope


def _walk_directory(dir_path: Path, max_files: int | None) -> list[Path]:
    found: list[Path] = []
    for root, dirnames, filenames in os.walk(dir_path):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIP_DIR_NAMES and not name.startswith(".")
        ]
        for name in sorted(filenames):
            path = Path(root) / name
            if not _is_reviewable_file(path):
                continue
            found.append(path)
            if max_files is not None and len(found) >= max_files:
                return found
    return found


def directory_scope(
    repo_root: Path,
    dir_path: Path,
    *,
    max_files: int | None = None,
) -> PathScope:
    """Build review scope for all eligible files under a directory."""
    root = repo_root.resolve()
    target = dir_path if dir_path.is_absolute() else root / dir_path
    if not target.is_dir():
        raise ValueError(f"directory not found: {dir_path}")

    files = _walk_directory(target, max_files)
    if not files:
        raise ValueError(f"no reviewable files under {dir_path}")

    rel_paths: list[str] = []
    changed_lines: dict[str, set[int]] = {}
    for path in files:
        rel = _rel_path(root, path)
        rel_paths.append(rel)
        changed_lines[rel] = _lines_for_file(path)

    rel_dir = _rel_path(root, target)
    scope = PathScope(
        scope_ref=f"path:{rel_dir}",
        changed_paths=rel_paths,
        changed_lines=changed_lines,
    )
    scope.path_prefixes = derive_path_prefixes(scope.changed_paths)
    return scope
