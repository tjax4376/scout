## Context

Scout indexes code into vector-searchable chunks with graph neighbors and exposes them via REST (`POST /search`, `GET /node/{id}`, `GET /spaces/list`). The existing `search_scout` skill targets general codebase exploration during agent coding sessions. AI code reviewers have a different workflow: they start from changed paths or review questions, need minimal context to judge correctness, and waste tokens when they read entire files. The user constraint is explicit: **no modifications to existing Scout features** (API, CLI behavior, setup wizard, `search_scout` skill, indexing, embed).

## Goals / Non-Goals

**Goals:**
- Ship a new agent skill `code-reviewer-scout` that instructs reviewers to use Scout REST API before full file reads
- Provide token-efficient review workflow: path-scoped search → snippet + neighbors → targeted node fetch → full file only as last resort
- Standalone install path (new module) for Cursor, Pi, OpenCode with `scout_api` / `default_space` injection
- Helper script for terminal/API calls during review (search with `path_prefix`, node lookup, spaces list, health)
- Tests for template content, install paths, injection, overwrite protection
- Deploy via existing CI pytest pipeline — no new infrastructure

**Non-Goals:**
- Changes to Scout REST API, `scout_core`, CLI commands, setup wizard, or `search_scout`
- New embed/index/search behavior or background jobs
- PR platform integrations (GitHub/GitLab webhooks, diff parsers)
- Automatic skill install during `scout setup` (would modify existing wizard)
- HTTP auth changes or new Scout serve endpoints

## Decisions

**Decision:** Add new skill directory `skills/code-reviewer-scout/` rather than extending `search_scout`.

**Rationale:** Keeps existing skill untouched; review workflow (escalation ladder, path scoping, stale-index guidance) is distinct enough to warrant separate SKILL.md.

**Alternative considered:** Add review section to `search_scout/SKILL.md` — rejected (modifies existing feature).

**Decision:** New Python module `scout/code_reviewer/install.py` with its own `AGENT_PATHS` and `install_code_reviewer_skill()`.

**Rationale:** Mirrors `scout/skill/install.py` pattern but isolated; no edits to existing install module. Independently testable per project module rules.

**Alternative considered:** Extend `scout/skill/install.py` with skill selector — rejected (modifies existing module).

**Decision:** Expose install via `python -m scout.code_reviewer.install` CLI entry (Typer or argparse in `__main__.py`).

**Rationale:** Avoids adding subcommands to main `scout` CLI (which could be seen as modifying existing CLI surface). Optional future: dedicated `scout code-reviewer install` if approved separately.

**Alternative considered:** Hook into setup wizard — rejected (modifies existing flow).

**Decision:** Skill helper script `scripts/review_api.py` — review-oriented wrapper over existing REST endpoints.

**Rationale:** Adds `path_prefix` and `kinds` flags prominently; documents review commands in SKILL.md. Uses stdlib `urllib` only (no new deps). Reads `SCOUT_API_URL` / injected config like `search_scout` helper.

**Decision:** Review escalation ladder documented in SKILL.md:

1. **Scope** — `path_prefix` to changed files/dirs from PR context
2. **Search** — `POST /search` with `top_k` 3–5, use snippets + neighbors
3. **Expand** — `GET /node/{id}` for one symbol when snippet truncated
4. **Full read** — IDE Read tool only when steps 1–3 insufficient (e.g., need full diff hunk, imports block, or cross-file refactor)

**Rationale:** Explicit token-saving policy agents can follow without new API fields.

**Decision:** Agent install paths follow existing conventions:

| Agent | Global | Project |
|-------|--------|---------|
| Cursor | `~/.cursor/skills/code-reviewer-scout/` | `<root>/.cursor/skills/code-reviewer-scout/` |
| Pi | `~/.pi/skills/code-reviewer-scout/` | `<root>/.pi/skills/code-reviewer-scout/` |
| OpenCode | `~/.config/opencode/skills/code-reviewer-scout/` | `<root>/.opencode/skills/code-reviewer-scout/` |

**Rationale:** Hyphen-only skill names required by agent platforms (Pi rejects underscores; apply same rule to all agents).

**Decision:** Template placeholders `{{SCOUT_API}}` and `{{DEFAULT_SPACE}}` injected at install time (same pattern as `search_scout`).

**Rationale:** Proven injection model; no runtime dependency on Scout Python package from skill files.

**Decision:** Overwrite protection — skip unless `--force` (same semantics as existing skill install).

**Rationale:** Prevents accidental clobber of user-customized skill copies.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Reviewers skip skill and read full files anyway | SKILL.md front-loads "always search first" rule; show token estimate in examples |
| Snippets too short for review judgment | Document node fetch step; neighbors surface call sites |
| Stale index misleads review | SKILL.md covers `X-Scout-Stale` header and `stale` field; suggest reindex if critical |
| Duplicate install logic vs `scout/skill` | Accept small duplication to honor no-modify constraint; shared extract later if approved |
| User forgets standalone install | README in skill + `scout/code_reviewer/README.md` with copy-paste commands |
| Agent name validation | Frontmatter `name: code-reviewer-scout` and directory `code-reviewer-scout` on all agents |

## Migration Plan

Greenfield additive change. No data migration. Users opt in by running install module. Rollback: delete installed skill directories.

## Open Questions

- Whether to add optional `scout code-reviewer install` subcommand in a follow-up change (requires CLI scope approval)
- Whether CI review bots (non-Cursor) need a separate minimal JSON workflow doc — defer to MVP unless requested
