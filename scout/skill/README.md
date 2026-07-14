# scout.skill

Installs the `search-scout`, `add-memory`, and `ask-scout` agent skills from repo templates into Cursor, Pi, or OpenCode paths.

## Entry point

- `install.py` — `install_skill()`, `AGENT_PATHS`, template injection

## Install paths

| Agent | Skill | Global | Project |
|-------|-------|--------|---------|
| cursor | search-scout | `~/.cursor/skills/search_scout` | `<project>/.cursor/skills/search_scout` |
| cursor | add-memory | `~/.cursor/skills/add_memory` | `<project>/.cursor/skills/add_memory` |
| cursor | ask-scout | `~/.cursor/skills/ask_scout` | `<project>/.cursor/skills/ask_scout` |
| pi | search-scout | `~/.pi/skills/search-scout` | `<project>/.pi/skills/search-scout` |
| pi | add-memory | `~/.pi/skills/add-memory` | `<project>/.pi/skills/add-memory` |
| pi | ask-scout | `~/.pi/skills/ask-scout` | `<project>/.pi/skills/ask-scout` |
| opencode | search-scout | `~/.config/opencode/skills/search_scout` | `<project>/.opencode/skills/search_scout` |
| opencode | add-memory | `~/.config/opencode/skills/add_memory` | `<project>/.opencode/skills/add_memory` |
| opencode | ask-scout | `~/.config/opencode/skills/ask_scout` | `<project>/.opencode/skills/ask_scout` |

**Pi naming:** directory and frontmatter `name` must use hyphens (`search-scout`, `add-memory`, `ask-scout`), not underscores.

## Templates

Source: `skills/search_scout/`, `skills/add_memory/`, and `skills/ask_scout/` in repo root. Setup copies and replaces:

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
