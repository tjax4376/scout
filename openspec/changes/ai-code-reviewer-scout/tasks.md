## 1. Skill template

- [x] 1.1 Create `skills/code-reviewer-scout/SKILL.md` with `name: code-reviewer-scout` frontmatter, review escalation ladder, REST examples, stale-index guidance, `{{SCOUT_API}}` / `{{DEFAULT_SPACE}}` placeholders
- [x] 1.2 Create `skills/code-reviewer-scout/README.md` with install instructions and agent compatibility notes
- [x] 1.3 Create `skills/code-reviewer-scout/scripts/review_api.py` — health, spaces list, path-scoped search (`path_prefix`, `kinds`), node lookup; stdlib only

## 2. Install module

- [x] 2.1 Create `scout/code_reviewer/install.py` with `AGENT_PATHS`, `skill_template_path()`, `install_code_reviewer_skill()` mirroring search_scout pattern
- [x] 2.2 Create `scout/code_reviewer/__main__.py` CLI: `--agent`, `--global`, `--project`, `--project-root`, `--scout-api`, `--default-space`, `--force`
- [x] 2.3 Create `scout/code_reviewer/README.md` documenting module purpose and usage

## 3. Tests

- [x] 3.1 Create `tests/code_reviewer/test_install.py` — template copy, injection, overwrite protection, `--force` replace
- [x] 3.2 Create `tests/code_reviewer/test_skill_template.py` — required files exist, SKILL.md contains escalation ladder and REST endpoint references
- [x] 3.3 Create `tests/code_reviewer/test_review_api.py` — argparse/usage and request URL construction (mocked HTTP)

## 4. Validation

- [x] 4.1 Run `pytest tests/code_reviewer/ -q` and full suite to confirm no regressions
- [x] 4.2 Run `python scripts/validate_openspec.py` to verify change artifacts
- [x] 4.3 Confirm no edits to `scout/skill/`, setup wizard, API routes, or `skills/search_scout/`; confirm skill name and paths use hyphens only

## 5. Docs

- [x] 5.1 Update `.memory/cards.md` with code reviewer skill install paths and workflow
- [x] 5.2 Journal entry `journal/2026-06-13-ai-code-reviewer-scout.md`
