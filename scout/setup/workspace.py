"""Workspace resolution — local path and git clone.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from scout.setup.api_url import repo_name_from_url, validate_git_url, validate_subdir_name
from scout.setup.prompts import console_print_red


def resolve_local_root() -> Path:
    """Prompt and validate local workspace root."""
    root = typer.prompt("Workspace root path", default=str(Path.cwd()))
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        console_print_red(f"invalid root: {root_path}")
        raise SystemExit(1)
    return root_path


def clone_git_workspace(
    *,
    force: bool = False,
    cwd: Path | None = None,
    git_url: str | None = None,
    subdir: str | None = None,
) -> Path:
    """Clone git repo into subdirectory of cwd."""
    base = cwd or Path.cwd()
    url = validate_git_url(git_url or typer.prompt("Git repository URL"))
    default_name = repo_name_from_url(url)
    name = validate_subdir_name(subdir or typer.prompt("Clone subdirectory", default=default_name))
    target = (base / name).resolve()

    if target.exists():
        if (target / ".git").is_dir() and not _dir_has_non_git_content(target):
            return target
        if any(target.iterdir()) and not force:
            console_print_red(
                f"target exists and is non-empty: {target} (use --force to replace)"
            )
            raise SystemExit(1)
        if force and target.exists():
            shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "git clone failed").strip()
        console_print_red(f"git clone failed: {stderr}")
        raise SystemExit(1)
    if not target.is_dir():
        console_print_red(f"clone did not create directory: {target}")
        raise SystemExit(1)
    return target


def _dir_has_non_git_content(path: Path) -> bool:
    """True if directory has content beyond .git metadata."""
    for child in path.iterdir():
        if child.name == ".git":
            continue
        return True
    return False
