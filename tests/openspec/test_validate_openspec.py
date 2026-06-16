"""Tests for scripts/validate_openspec.py."""

from __future__ import annotations

from pathlib import Path

from scripts.validate_openspec import (
    extract_api_contracts_endpoints,
    extract_app_routes,
    extract_rest_api_spec_endpoints,
    validate_api_contracts_sync,
    validate_app_routes_sync,
    validate_change_structure,
    validate_markdown_links,
    validate_openspec,
)


def test_validate_openspec_passes_on_repo(tmp_path: Path) -> None:
    """Real openspec tree in repo must satisfy decision B rules."""
    repo_root = Path(__file__).resolve().parents[2]
    result = validate_openspec(repo_root / "openspec")
    assert result.ok, result.errors


def test_structure_rejects_missing_proposal(tmp_path: Path) -> None:
    change = tmp_path / "bad-change"
    change.mkdir()
    (change / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    (change / "design.md").write_text("# d\n", encoding="utf-8")
    (change / "tasks.md").write_text("# t\n", encoding="utf-8")
    specs = change / "specs" / "foo"
    specs.mkdir(parents=True)
    (specs / "spec.md").write_text(
        "## ADDED Requirements\n\n#### Scenario: ok\n- **WHEN** x\n- **THEN** y\n",
        encoding="utf-8",
    )

    errors = validate_change_structure(change)
    assert any("missing required file proposal.md" in e for e in errors)


def test_structure_requires_scenario_blocks(tmp_path: Path) -> None:
    change = tmp_path / "no-scenario"
    change.mkdir()
    for name in ("proposal.md", "design.md", "tasks.md", ".openspec.yaml"):
        (change / name).write_text("x\n", encoding="utf-8")
    specs = change / "specs" / "bar"
    specs.mkdir(parents=True)
    (specs / "spec.md").write_text("## ADDED Requirements\n\n### Requirement: r\n", encoding="utf-8")

    errors = validate_change_structure(change)
    assert any("no #### Scenario:" in e for e in errors)


def test_links_reject_broken_relative(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("[bad](../missing/spec.md)\n", encoding="utf-8")
    errors = validate_markdown_links(tmp_path)
    assert len(errors) == 1
    assert "broken link" in errors[0]


def test_links_allow_external_urls(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("[ext](https://example.com/page)\n", encoding="utf-8")
    assert validate_markdown_links(tmp_path) == []


def test_api_contracts_sync_passes_on_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    errors = validate_api_contracts_sync(repo_root)
    assert errors == [], errors


def test_api_contracts_sync_detects_drift(tmp_path: Path) -> None:
    contracts = tmp_path / "api-contracts.md"
    contracts.write_text(
        "## Endpoints\n\n"
        "| Method | Path | Description |\n"
        "|--------|------|-------------|\n"
        "| `GET` | `/v1/health` | ok |\n"
        "| `GET` | `/v1/spaces/list` | list |\n",
        encoding="utf-8",
    )
    ospec = tmp_path / "openspec"
    spec_dir = ospec / "specs" / "rest-api"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "## Requirements\n\n"
        "#### Scenario: health\n"
        "- **WHEN** client sends `GET /v1/health`\n"
        "- **THEN** ok\n",
        encoding="utf-8",
    )
    errors = validate_api_contracts_sync(tmp_path, ospec)
    assert any("spaces/list" in e for e in errors)


def test_normalize_space_slug_in_path() -> None:
    eps = extract_rest_api_spec_endpoints(
        "- **WHEN** client sends `POST /v1/spaces/myapp/search`\n"
    )
    assert ("POST", "/v1/spaces/{space}/search") in eps


def test_app_routes_sync_passes_on_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    errors = validate_app_routes_sync(repo_root)
    assert errors == [], errors


def test_app_routes_sync_detects_extra_route(tmp_path: Path) -> None:
    contracts = tmp_path / "api-contracts.md"
    contracts.write_text(
        "## Endpoints\n\n| Method | Path | Description |\n"
        "|--------|------|-------------|\n| `GET` | `/v1/health` | ok |\n",
        encoding="utf-8",
    )
    app_dir = tmp_path / "scout" / "api"
    app_dir.mkdir(parents=True)
    (app_dir / "app.py").write_text(
        '@app.get("/v1/health")\n@app.get("/v1/extra")\n',
        encoding="utf-8",
    )
    app_eps = extract_app_routes((app_dir / "app.py").read_text(encoding="utf-8"))
    contract_eps = extract_api_contracts_endpoints(contracts.read_text(encoding="utf-8"))
    assert ("GET", "/v1/extra") in app_eps - contract_eps


def test_extract_app_routes_normalizes_params() -> None:
    text = '@app.post("/v1/spaces/{space}/search")\n'
    assert ("POST", "/v1/spaces/{space}/search") in extract_app_routes(text)
