# search-scout skill (maintainer docs)

Agent skill template installed by `scout <space> setup`. Agents read `SKILL.md` to call Scout REST API.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Agent-facing instructions (injected at install) |

## Install flow

1. User runs `scout myapp setup` (or `--agent cursor|pi|opencode`)
2. `scout.skill.install.install_skill()` copies this directory to agent path
3. Placeholders replaced:
   - `{{SCOUT_API}}` → `api_base_url` from `.scout/config.yaml`
   - `{{DEFAULT_SPACE}}` → space name from setup

## Agent paths

See `scout/skill/README.md` for global vs project paths per agent.

## Pi constraint

Frontmatter `name: search-scout` (hyphens). Directory `search-scout`. Pi rejects underscores.

## Contract reference

Full API shapes: [`api-contracts.md`](../../api-contracts.md)

## Tests

`tests/integration/test_skill.py`

## Specs

- `openspec/changes/scout-simple-mvp1/specs/agent-skill/spec.md`
