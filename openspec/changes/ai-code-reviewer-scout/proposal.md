## Why

AI code reviewers (Cursor agents, PR bots, CI review tools) typically read whole files into session context to understand changed code, which burns context tokens and slows reviews on large codebases. Scout already maintains an in-memory code index — petgraph structure plus sqlite-vec embeddings — that serves symbol snippets, breadcrumbs, and graph neighbors (imports, calls, contains) via REST without loading source files into the agent session. There is no agent skill or workflow tailored for review tasks that prefers this index over file reads. A dedicated code-reviewer skill instructs reviewers to load references from Scout's in-memory index first (search hits, neighbor nodes, targeted node lookup) and only pull full files when indexed snippets are insufficient, materially reducing loaded tokens without changing Scout core behavior.

## What Changes

- Add new repo skill `skills/code-reviewer-scout/` with review-focused workflow: use Scout in-memory index as primary context source instead of reading files into session; scope by path, search symbols, fetch indexed snippets and graph neighbors, escalate to full file read only when needed
- Instruct reviewers to query Scout REST (`/search`, `/node/{id}`) for code references — snippets, symbols, structural neighbors — rather than loading entire source files into context
- Add standalone install helper (new module) that copies/injects the skill into Cursor, Pi, and OpenCode paths — separate from existing `search_scout` setup flow
- Add optional helper script(s) in the skill for common review API calls (search, node lookup, spaces list) — REST-only, no pyo3 or shared services
- Document review playbooks: index-first context loading, PR diff scoping, stale-index handling, neighbor traversal for call-site context
- Add tests for skill template, install helper, and injection logic
- **No changes** to existing Scout features: REST API, CLI commands, `search_scout` skill, setup wizard, indexing, in-memory graph, or embed behavior

## Capabilities

### New Capabilities

- `code-reviewer-skill`: Agent skill definition, index-first review workflow (Scout in-memory graph/vector index over file reads), REST usage patterns, and install paths for AI code reviewers

### Modified Capabilities

<!-- None — existing Scout capabilities unchanged per constraint -->

## Impact

- New: `skills/code-reviewer-scout/` (SKILL.md, README, optional scripts)
- New: `scout/code_reviewer/` install module (or equivalent standalone module) — does not modify `scout/skill/install.py`
- New: `tests/code_reviewer/` for install and template validation
- CI: include new tests in existing pytest pipeline
- Relies on existing Scout in-memory index (petgraph + sqlite-vec) served via REST — no new index or graph implementation
- No API contract changes, no `scout_core` changes, no setup wizard changes
