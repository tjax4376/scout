# scout.skill

Installs the `search-scout` agent skill from repo template into Cursor, Pi, or OpenCode paths.

## Entry point

- `install.py` — `install_skill()`, `AGENT_PATHS`, template injection

## Install paths

| Agent | Global | Project |
|-------|--------|---------|
| cursor | `~/.cursor/skills/search_scout` | `<project>/.cursor/skills/search_scout` |
| pi | `~/.pi/skills/search-scout` | `<project>/.pi/skills/search-scout` |
| opencode | `~/.config/opencode/skills/search_scout` | `<project>/.opencode/skills/search_scout` |

**Pi naming:** directory and frontmatter `name` must use hyphens (`search-scout`), not underscores.

## Template

Source: `skills/search_scout/` in repo root. Setup copies and replaces:

- `{{SCOUT_API}}` → configured base URL (e.g. `http://127.0.0.1:8741/v1`)
- `{{DEFAULT_SPACE}}` → space name from setup wizard

## Invocation

Called by `scout <space> setup` after index completes. `--agent cursor|pi|opencode` skips interactive agent picker.

## Dependencies

- **Python:** stdlib only (shutil, pathlib)
- **Internal:** none (REST-only boundary to agents)

## Tests

`tests/integration/test_skill.py`

## Specs

- `openspec/changes/scout-simple-mvp1/specs/agent-skill/spec.md`
- `openspec/changes/scout-unified-setup/specs/agent-skill/spec.md`
