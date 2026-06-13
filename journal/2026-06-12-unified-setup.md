# Journal — Unified Scout Setup

**Date:** 2026-06-12  
**Metadata:** v0.1.0 | Scout Contributors | unified-setup wizard

## Context

User requested one setup process with four branches (local/git × local-embed/OpenRouter), configurable Scout API base URL at every setup, git clone to cwd subdirectory, leave-blank API key prompts, and skill always updated with `scout_api`.

## Discussion points

- Scout API URL: full `http(s)://host:port/v1` prompt (not IP-only); stored as `api_base_url`; `scout serve` binds parsed host/port
- Git clone destination: subdirectory of current working directory (user choice)
- Branches presented as single menu (1–4) rather than two-step axis selection
- Agent skill install mandatory after index; `--agent` flag retained for CI
- OpenSpec change `scout-unified-setup` created before implementation

## Code changed

| Area | Files |
|------|-------|
| Config | `scout/config.py` — `api_base_url` field, load migration |
| Setup module | `scout/setup/api_url.py`, `prompts.py`, `workspace.py`, `embed.py`, `runner.py` |
| CLI | `scout/cli/main.py` — delegate setup to runner; serve from parsed URL |
| OpenSpec | `openspec/changes/scout-unified-setup/` |
| Tests | `tests/test_setup.py`, `tests/test_integration.py` |
| Docs | `README.md`, `.memory/cards.md` |

## Test plan

- URL normalize/parse/migration
- Branch enum flags
- Git URL/subdir validation; clone success/failure (mocked)
- API key blank-to-keep prompts
- Skill injection with custom base URL
- Serve bind host/port from config
