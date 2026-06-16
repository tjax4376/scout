"""Git diff scope parsing for Hawkeye.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiffScope:
    diff_ref: str
    changed_paths: list[str] = field(default_factory=list)
    changed_lines: dict[str, set[int]] = field(default_factory=dict)
    path_prefixes: list[str] = field(default_factory=list)


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_PATH = re.compile(r"^\+\+\+ b/(.*)$")


def parse_diff_output(text: str, diff_ref: str) -> DiffScope:
    scope = DiffScope(diff_ref=diff_ref)
    current_path: str | None = None
    current_line = 0
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        path_match = _PATH.match(line)
        if path_match:
            current_path = path_match.group(1).strip()
            if current_path and current_path not in scope.changed_paths:
                scope.changed_paths.append(current_path)
            scope.changed_lines.setdefault(current_path, set())
            continue
        hunk = _HUNK.match(line)
        if hunk:
            current_line = int(hunk.group(1))
            continue
        if current_path is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            scope.changed_lines[current_path].add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        elif line.startswith(" "):
            current_line += 1
    scope.path_prefixes = derive_path_prefixes(scope.changed_paths)
    return scope


def derive_path_prefixes(changed_paths: list[str]) -> list[str]:
    prefixes: set[str] = set()
    for rel in changed_paths:
        norm = rel.replace("\\", "/")
        prefixes.add(norm)
        if "/" in norm:
            parts = norm.split("/")
            for i in range(1, len(parts)):
                prefixes.add("/".join(parts[:i]) + "/")
        else:
            prefixes.add("")
    return sorted(prefixes, key=lambda p: (p.count("/"), p))


def git_diff_scope(repo_root: Path, diff_ref: str) -> DiffScope:
    cmd = ["git", "diff", "--unified=0", diff_ref, "--"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"git diff failed: {exc}") from exc
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.strip() or f"git diff exit {proc.returncode}")
    return parse_diff_output(proc.stdout, diff_ref)


def map_changed_symbols(
    symbols: list[dict],
    changed_lines: dict[str, set[int]],
) -> list[dict]:
    out: list[dict] = []
    for sym in symbols:
        rel = str(sym.get("rel_path") or "")
        changed = changed_lines.get(rel, set())
        if not changed:
            continue
        start = int(sym.get("start_line") or 0)
        end = int(sym.get("end_line") or start)
        if any(start <= ln <= end for ln in changed):
            out.append(sym)
    return out
