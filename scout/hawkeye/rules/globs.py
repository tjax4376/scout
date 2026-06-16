"""Path glob helpers for Hawkeye rules.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Normalize path separators via Path.as_posix().
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path


def path_matches(glob_pattern: str, rel_path: str) -> bool:
    norm = Path(rel_path.replace("\\", "/")).as_posix().lstrip("./")
    pat = Path(glob_pattern.replace("\\", "/")).as_posix()
    if pat.startswith("**/"):
        tail = pat[3:]
        if fnmatch.fnmatchcase(norm, tail):
            return True
        if "/" in tail:
            anchor = tail.split("/")[0]
            for idx, part in enumerate(norm.split("/")):
                if part == anchor:
                    sub = "/".join(norm.split("/")[idx:])
                    if fnmatch.fnmatchcase(sub, tail):
                        return True
        return False
    return fnmatch.fnmatchcase(norm, pat)


def symbol_matches_regex(pattern: str | None, symbol: str | None) -> bool:
    if not pattern:
        return True
    return bool(re.search(pattern, symbol or ""))
