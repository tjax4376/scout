# Journal: AI Code Reviewer Scout

**Date:** 2026-06-13  
**Author:** Cursor Agent  
**Version:** implementation v1.0  
**Change:** `openspec/changes/ai-code-reviewer-scout/`

## Context

Feature for AI code reviewers to use Scout in-memory index (petgraph + sqlite-vec) via REST instead of loading full files into session context — reduces review tokens. Constraint: no changes to existing Scout features.

## Discussion Points

1. **Problem:** Code review agents read full files into session → high token burn.
2. **Existing asset:** Scout in-memory index serves snippets, breadcrumbs, graph neighbors via REST.
3. **Gap:** No review-specific agent skill directing index-first context loading.
4. **Naming:** Skill name and install paths use hyphens only (`code-reviewer-scout`).
5. **Workflow:** Escalation ladder — path-scoped search → snippets/neighbors → node fetch → full file read last resort.
6. **Integration:** REST-only; standalone install module separate from `scout/skill/` and setup wizard.

## Code Changed

| Area | Files |
|------|-------|
| Skill template | `skills/code-reviewer-scout/SKILL.md`, `README.md`, `scripts/review_api.py` |
| Install module | `scout/code_reviewer/install.py`, `__main__.py`, `README.md` |
| Tests | `tests/code_reviewer/test_install.py`, `test_skill_template.py`, `test_review_api.py` |
| OpenSpec | All artifacts in `openspec/changes/ai-code-reviewer-scout/` (tasks marked complete) |
| Docs | `.memory/cards.md` |

**Not modified:** `scout/skill/`, setup wizard, API routes, `skills/search_scout/`, CLI main commands.

## Summary

Shipped `code-reviewer-scout` agent skill and `python -m scout.code_reviewer` standalone installer. Reviewers query Scout index first; 16 new tests pass; full suite 76 pass; OpenSpec validation pass.

## Test Plan

- [x] `pytest tests/code_reviewer/ -q` — 16 passed
- [x] `pytest -q` — 76 passed (no regressions)
- [x] `python scripts/validate_openspec.py` — passed
- [x] Verified no edits to existing scout features

**Manual (optional):**
```bash
python -m scout.code_reviewer --agent cursor --project --project-root . \
  --scout-api http://127.0.0.1:8741/v1 --default-space scout --force
python skills/code-reviewer-scout/scripts/review_api.py search scout "embed batch" --path-prefix scout/
```
