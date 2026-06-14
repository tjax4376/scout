# Journal: Code review improvements (Batch A + B)

**Date:** 2026-06-12  
**Author:** Cursor agent  
**Version:** docs/tests reorg v1

## Context

Code review flagged weak docs/organization: flat test dir, uncommented Cargo.toml, thin skill docs, no API test conventions, missing component READMEs, no OpenSpec cross-refs, no PR template. User requested Batch A (docs) + Batch B (test reorg) immediately; Batch C (OpenSpec validation) deferred to sequential decisions.

## Discussion points

1. **Test layout** — split monolithic `test_integration.py` into domain subdirs; shared `conftest.py` + `api/conftest.py` for standardized FastAPI fixtures.
2. **Component READMEs** — one per major module: `scout_core/`, `scout/api/`, `scout/skill/`, `tests/`, `skills/search_scout/`.
3. **Cargo comments** — inline rationale for workspace, crate-type, extension-module feature, each dependency.
4. **Skill docs** — expanded `SKILL.md` with install paths, injection table, troubleshooting, Pi hyphen rule.
5. **OpenSpec cross-refs** — `See also:` block at top of all MVP1 + unified-setup + stop-serve spec files.
6. **PR template** — checklist for pytest, cargo, api-contracts, OpenSpec tasks.

## Code changed

| Area | Files |
|------|-------|
| Tests reorg | `tests/conftest.py`, `tests/api/`, `tests/cli/`, `tests/embed/`, `tests/integration/`; deleted flat `test_*.py` |
| READMEs | `scout_core/README.md`, `scout/api/README.md`, `scout/skill/README.md`, `tests/README.md`, `skills/search_scout/README.md` |
| Cargo | `Cargo.toml`, `scout_core/Cargo.toml` — comment blocks |
| Skill | `skills/search_scout/SKILL.md` — install/troubleshooting sections |
| OpenSpec | 13 spec files — cross-reference headers |
| CI/docs | `.github/pull_request_template.md` |

**Verification:** `pytest -q` → 39 passed.

## Next (Batch C)

OpenSpec automated validation — decisions pending one at a time.
