"""CLI entry: python -m scout.code_reviewer

Metadata: v0.1.0 | Scout Contributors | 2026-06-13
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scout.code_reviewer.install import install_code_reviewer_skill


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install code-reviewer-scout agent skill (standalone; not scout setup)",
    )
    parser.add_argument("--agent", required=True, choices=["cursor", "pi", "opencode"])
    parser.add_argument("--global", dest="global_install", action="store_true")
    parser.add_argument("--project", dest="project_install", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scout-api", required=True, help="Scout API base URL including /v1")
    parser.add_argument("--default-space", required=True, help="Default Scout space name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing install")
    args = parser.parse_args(argv)

    if not args.global_install and not args.project_install:
        parser.error("specify --global and/or --project")

    try:
        dests = install_code_reviewer_skill(
            args.agent,
            global_install=args.global_install,
            project_install=args.project_install,
            project_root=args.project_root,
            scout_api=args.scout_api,
            default_space=args.default_space,
            force=args.force,
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for dest in dests:
        print(f"installed: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
