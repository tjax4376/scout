#!/usr/bin/env python3
"""Validate OpenSpec change structure and markdown link integrity.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
Rationale: Batch C — structure + links (B) + api-contracts sync (C) + app.py routes (C4).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Required top-level files per change directory under openspec/changes/
REQUIRED_CHANGE_FILES = ("proposal.md", "design.md", "tasks.md", ".openspec.yaml")

# At least one requirements heading must appear in each spec.md
REQUIREMENTS_HEADINGS = ("## ADDED Requirements", "## MODIFIED Requirements")

# Markdown link: [label](target) — http(s) and anchors skipped at resolve time
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Each spec with requirements must document at least one scenario
SCENARIO_HEADING = "#### Scenario:"

# api-contracts.md endpoints table row: | `GET` | `/v1/health` | ...
CONTRACTS_TABLE_ROW_RE = re.compile(
    r"^\|\s*`(GET|POST|PUT|DELETE|PATCH)`\s*\|\s*`([^`]+)`\s*\|",
    re.MULTILINE,
)

# Explicit method + /v1 path in prose (scenarios, requirements)
HTTP_ENDPOINT_RE = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/v1/[A-Za-z0-9_./{}-]+)",
    re.IGNORECASE,
)

# Requirement lines: expose `POST /v1/spaces/{space}/search`
EXPOSE_ENDPOINT_RE = re.compile(
    r"expose `(GET|POST|PUT|DELETE|PATCH)\s+([^`]+)`",
    re.IGNORECASE,
)

# Canonical rest-api spec path(s) under openspec/changes/
REST_API_SPEC_GLOB = "changes/*/specs/rest-api/spec.md"

# FastAPI route decorators on app: @app.get("/v1/health")
APP_ROUTE_RE = re.compile(
    r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

DEFAULT_API_APP = Path("scout/api/app.py")


@dataclass
class ValidationResult:
    """Collected errors from structure and link checks."""

    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def default_openspec_root() -> Path:
    """Repo openspec/ relative to this script (scripts/ → repo root)."""
    return Path(__file__).resolve().parents[1] / "openspec"


def default_repo_root() -> Path:
    """Repository root (parent of scripts/)."""
    return Path(__file__).resolve().parents[1]


def find_change_dirs(changes_root: Path) -> list[Path]:
    """Return change directories that contain .openspec.yaml."""
    if not changes_root.is_dir():
        return []
    return sorted(
        p for p in changes_root.iterdir() if p.is_dir() and (p / ".openspec.yaml").is_file()
    )


def validate_change_structure(change_dir: Path) -> list[str]:
    """Check required files, specs/ tree, requirements headings, scenarios."""
    errors: list[str] = []
    name = change_dir.name

    for filename in REQUIRED_CHANGE_FILES:
        if not (change_dir / filename).is_file():
            errors.append(f"{name}: missing required file {filename}")

    specs_dir = change_dir / "specs"
    if not specs_dir.is_dir():
        errors.append(f"{name}: missing specs/ directory")
        return errors

    spec_files = sorted(specs_dir.rglob("spec.md"))
    if not spec_files:
        errors.append(f"{name}: specs/ contains no spec.md files")
        return errors

    for spec_path in spec_files:
        rel = spec_path.relative_to(change_dir)
        text = spec_path.read_text(encoding="utf-8")

        if not any(h in text for h in REQUIREMENTS_HEADINGS):
            errors.append(f"{name}/{rel}: missing ADDED or MODIFIED Requirements section")

        if any(h in text for h in REQUIREMENTS_HEADINGS) and SCENARIO_HEADING not in text:
            errors.append(f"{name}/{rel}: requirements present but no #### Scenario: blocks")

    return errors


def _is_external_link(target: str) -> bool:
    """Skip URLs, mailto, and same-page anchors."""
    lowered = target.strip().lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("#")
    )


def extract_relative_links(md_path: Path) -> list[tuple[str, str]]:
    """Return (target, source_relative) for each relative markdown link in file."""
    text = md_path.read_text(encoding="utf-8")
    found: list[tuple[str, str]] = []
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if _is_external_link(target):
            continue
        # Strip optional title after space: path "title"
        target = target.split()[0]
        found.append((target, str(md_path)))
    return found


def normalize_api_path(path: str) -> str:
    """Normalize concrete space/node examples to template segments."""
    path = path.strip().rstrip(".,;:`\"')")
    path = re.sub(
        r"/v1/spaces/[^/\s`\"']+/(search|reindex|node/)",
        r"/v1/spaces/{space}/\1",
        path,
    )
    path = re.sub(r"/node/[^/\s`\"']+", "/node/{node_id}", path)
    return path


def extract_api_contracts_endpoints(text: str) -> set[tuple[str, str]]:
    """Parse Method+Path pairs from api-contracts.md endpoints table."""
    endpoints: set[tuple[str, str]] = set()
    for method, path in CONTRACTS_TABLE_ROW_RE.findall(text):
        endpoints.add((method.upper(), normalize_api_path(path)))
    return endpoints


def extract_rest_api_spec_endpoints(text: str) -> set[tuple[str, str]]:
    """Parse Method+Path pairs from rest-api OpenSpec scenarios and requirements."""
    endpoints: set[tuple[str, str]] = set()
    for method, path in HTTP_ENDPOINT_RE.findall(text):
        endpoints.add((method.upper(), normalize_api_path(path)))
    for method, path in EXPOSE_ENDPOINT_RE.findall(text):
        endpoints.add((method.upper(), normalize_api_path(path.strip())))
    return endpoints


def find_rest_api_specs(openspec_root: Path) -> list[Path]:
    """All rest-api/spec.md files across active changes."""
    return sorted(openspec_root.glob(REST_API_SPEC_GLOB))


def validate_api_contracts_sync(
    repo_root: Path | None = None,
    openspec_root: Path | None = None,
) -> list[str]:
    """Fail if api-contracts.md endpoint table diverges from rest-api/spec.md."""
    root = repo_root or default_repo_root()
    ospec = openspec_root or root / "openspec"

    errors: list[str] = []
    contract_eps = load_api_contracts_endpoints(root)
    if contract_eps is None:
        return ["api-contracts.md not found at repo root"]

    spec_files = find_rest_api_specs(ospec)
    if not spec_files:
        return ["no rest-api/spec.md found under openspec/changes/"]

    spec_eps: set[tuple[str, str]] = set()
    for spec_path in spec_files:
        spec_eps |= extract_rest_api_spec_endpoints(
            spec_path.read_text(encoding="utf-8")
        )

    for method, path in sorted(contract_eps - spec_eps):
        errors.append(
            f"api-contracts.md lists {method} {path} but rest-api/spec.md does not"
        )
    for method, path in sorted(spec_eps - contract_eps):
        errors.append(
            f"rest-api/spec.md lists {method} {path} but api-contracts.md does not"
        )
    return errors


def extract_app_routes(text: str) -> set[tuple[str, str]]:
    """Parse Method+Path from @app.{method}(\"path\") decorators."""
    endpoints: set[tuple[str, str]] = set()
    for method, path in APP_ROUTE_RE.findall(text):
        endpoints.add((method.upper(), normalize_api_path(path)))
    return endpoints


def load_api_contracts_endpoints(repo_root: Path) -> set[tuple[str, str]] | None:
    """Load normalized endpoints from api-contracts.md, or None if missing."""
    contracts_path = repo_root / "api-contracts.md"
    if not contracts_path.is_file():
        return None
    return extract_api_contracts_endpoints(contracts_path.read_text(encoding="utf-8"))


def validate_app_routes_sync(repo_root: Path | None = None) -> list[str]:
    """Fail if scout/api/app.py routes diverge from api-contracts.md table."""
    root = repo_root or default_repo_root()
    app_path = root / DEFAULT_API_APP
    errors: list[str] = []

    contract_eps = load_api_contracts_endpoints(root)
    if contract_eps is None:
        return ["api-contracts.md not found at repo root"]
    if not app_path.is_file():
        return [f"{DEFAULT_API_APP} not found"]

    app_eps = extract_app_routes(app_path.read_text(encoding="utf-8"))

    for method, path in sorted(contract_eps - app_eps):
        errors.append(
            f"api-contracts.md lists {method} {path} but {DEFAULT_API_APP} does not"
        )
    for method, path in sorted(app_eps - contract_eps):
        errors.append(
            f"{DEFAULT_API_APP} lists {method} {path} but api-contracts.md does not"
        )
    return errors


def validate_markdown_links(openspec_root: Path) -> list[str]:
    """Resolve every relative link under openspec/ to a real file."""
    errors: list[str] = []
    for md_path in sorted(openspec_root.rglob("*.md")):
        for target, source in extract_relative_links(md_path):
            resolved = (md_path.parent / target).resolve()
            if not resolved.is_file():
                rel_source = md_path.relative_to(openspec_root)
                errors.append(f"{rel_source}: broken link [{target}] → {resolved}")
    return errors


def validate_openspec(
    openspec_root: Path | None = None,
    repo_root: Path | None = None,
) -> ValidationResult:
    """Run structure, link, and api-contracts sync checks."""
    root = openspec_root or default_openspec_root()
    repo = repo_root or default_repo_root()
    result = ValidationResult()

    changes_root = root / "changes"
    change_dirs = find_change_dirs(changes_root)
    if not change_dirs:
        result.errors.append(f"no change directories found under {changes_root}")
        return result

    for change_dir in change_dirs:
        result.errors.extend(validate_change_structure(change_dir))

    result.errors.extend(validate_markdown_links(root))
    result.errors.extend(validate_api_contracts_sync(repo, root))
    result.errors.extend(validate_app_routes_sync(repo))
    return result


def main() -> int:
    """CLI entry: exit 0 on success, 1 with error listing on failure."""
    result = validate_openspec()
    if result.ok:
        print("OpenSpec validation passed.")
        return 0
    print("OpenSpec validation failed:", file=sys.stderr)
    for err in result.errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
