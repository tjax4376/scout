# Journal: OpenSpec validation (Batch C decision B)

**Date:** 2026-06-12  
**Author:** Cursor agent

## Context

User chose Batch C option **B**: validate OpenSpec structure (required change files, requirements sections, scenarios) plus markdown link integrity. Cross-change `See also:` links from prior session had wrong relative paths (`../../` vs `../../../`).

## Discussion points

1. Validator as standalone script `scripts/validate_openspec.py` — no new Python package module; importable for tests via repo-root pythonpath.
2. CI step before pytest in `.github/workflows/ci.yml`.
3. Fixed 7 broken cross-change spec links discovered during implementation.
4. PR template checklist updated with validator command.

## Code changed

| File | Change |
|------|--------|
| `scripts/validate_openspec.py` | Structure + link validation CLI |
| `tests/openspec/test_validate_openspec.py` | Unit tests + repo integration test |
| `.github/workflows/ci.yml` | `python scripts/validate_openspec.py` step |
| `.github/pull_request_template.md` | OpenSpec validator checkbox |
| `openspec/changes/**/spec.md` | Fixed cross-change relative links |

**Verification:** `python scripts/validate_openspec.py` → pass; `pytest -q` → 44 passed.

## Batch C decision 2 (B+D) — local discoverability

- `scripts/scout.sh validate` — wraps validator script
- `Makefile` — `make validate-openspec`, `make test`
- README dev section — documents all entry points

## Batch C decision 3 (C) — api-contracts sync

- Validator compares `api-contracts.md` endpoints table ↔ `openspec/.../rest-api/spec.md`
- Normalizes `{space}` slug examples before diff
- Added missing `GET /v1/spaces/list` requirement to rest-api spec (drift fix)
- Tests: sync pass, drift detection, path normalization

## Batch C decision 4 (C) — app.py route sync

- `validate_app_routes_sync()` — parses `@app.{method}("path")` in `scout/api/app.py`
- Symmetric diff vs `api-contracts.md` endpoints table
- Full chain: spec ↔ contracts ↔ app.py

## Batch C complete

Decisions B, B+D, C (spec sync), C (app sync) shipped. Optional future: SKILL.md endpoint table sync, pre-commit hook.
