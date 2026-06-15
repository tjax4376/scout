# search-scout skill (maintainer docs)

Agent skill template installed by `scout <space> setup`. Agents read `SKILL.md` to call Scout REST API.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Agent-facing instructions (injected at install) |
| `scripts/scout_api.py` | Terminal helper for REST calls |

## API URL resolution (`scout_api.py`)

1. `SCOUT_API_URL` environment variable
2. `api_base_url` from `~/.scout/config.yaml`
3. Default: `http://127.0.0.1:8747/v1`

Config/env always win over the 8747 default. Re-run setup to refresh injected skill URL after port change.

## Install flow

1. User runs `scout myapp setup` from **repo root** (workspace default `.`, optional `src/` picker)
2. `scout.skill.install.install_skill()` copies this directory to agent path
3. Placeholders replaced:
   - `{{SCOUT_API}}` → `api_base_url` from `.scout/config.yaml`
   - `{{DEFAULT_SPACE}}` → space name from setup

## Graph vs session search

| Mode | Serve | Search |
|------|-------|--------|
| Graph-only | `scout serve` | 503 — use `/symbols` + `/file` |
| Session embed | `scout serve --embed` | Hits from files read via `GET /file`; `compressed_text` on hits |

## Agent paths

See `scout/skill/README.md` for global vs project paths per agent.

## Pi constraint

Frontmatter `name: search-scout` (hyphens). Directory `search-scout`. Pi rejects underscores.

## Contract reference

Full API shapes: [`api-contracts.md`](../../api-contracts.md)

## Tests

- `tests/integration/test_skill.py`
- `tests/skills/test_scout_api.py`

## Specs

- `openspec/changes/search-scout-port-8747/`
- `openspec/changes/session-embed-on-read/`
- `openspec/changes/embed-chunk-compression/`
