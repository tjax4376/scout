"""Workspace resolution — local path, git clone, source folder picker.

Metadata: v0.1.1 | Scout Contributors | 2026-06-14
Change: cwd `.` shorthand + index subdirectory picker for monorepos.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from scout.setup.api_url import repo_name_from_url, validate_git_url, validate_subdir_name
from scout.setup.prompts import console_print, console_print_red

# Immediate child dirs hidden from source-folder suggestions (not from indexing).
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".scout",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".cursor",
        ".idea",
        ".vscode",
        "vendor",
    }
)


def resolve_path_input(raw: str, *, base: Path | None = None) -> Path:
    """Resolve `.`, `./`, relative, or absolute path to an existing directory."""
    anchor_base = base or Path.cwd()
    trimmed = raw.strip() or "."
    path = Path(trimmed).expanduser()
    if not path.is_absolute():
        path = (anchor_base / path).resolve()
    else:
        path = path.resolve()
    if not path.is_dir():
        console_print_red(f"invalid root: {path}")
        raise SystemExit(1)
    return path


def resolve_local_root() -> Path:
    """Prompt workspace anchor; default `.` = cwd (run setup from repo root)."""
    cwd = Path.cwd().resolve()
    console_print("Run setup from your repository top level.")
    console_print(f"Current directory: {cwd}")
    raw = typer.prompt("Workspace root path", default=".")
    return resolve_path_input(raw, base=cwd)


def discover_source_folders(anchor: Path) -> list[Path]:
    """List immediate child directories suitable as index roots."""
    if not anchor.is_dir():
        return []
    folders: list[Path] = []
    for child in sorted(anchor.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name in EXCLUDED_DIR_NAMES:
            continue
        folders.append(child)
    return folders


def prompt_index_subdirectory(anchor: Path) -> Path:
    """Pick index root under anchor; option 0 keeps entire workspace."""
    folders = discover_source_folders(anchor)
    if not folders:
        return anchor

    console_print("Select folder to index:")
    console_print("  0) . (entire workspace)")
    for index, folder in enumerate(folders, start=1):
        console_print(f"  {index}) {folder.name}/")

    default = "0"
    while True:
        choice = typer.prompt("Select folder", default=default).strip()
        if choice in {"", "0", "."}:
            return anchor
        try:
            selected = int(choice)
        except ValueError:
            console_print_red("invalid selection — enter a number from the list")
            continue
        if 1 <= selected <= len(folders):
            return folders[selected - 1].resolve()
        console_print_red("invalid selection — enter a number from the list")


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
