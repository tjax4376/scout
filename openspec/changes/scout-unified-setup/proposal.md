## Why

MVP1 setup is linear and localhost-only: no configurable Scout API URL, no git-clone workspace branch, agent skill install gated on `--agent` flag, and API-key prompts don't clearly offer leave-blank-to-keep. Agents need one wizard that covers four file-source × embed-provider combinations and always injects the configured API base URL into the search_scout skill.

## What Changes

- Unified `scout <space> setup` wizard with 4 branches (local/git × local-embed/openrouter)
- User-specified full Scout API base URL (`http(s)://host:port/v1`) stored in config; `scout serve` binds host/port from URL
- Git clone workspace source into cwd subdirectory (branches 3–4)
- API-key prompts offer leave blank when key exists for provider (and show stored model)
- Interactive agent selection every setup; skill install always runs with injected `scout_api`
- New `scout/setup/` module for testable orchestration

## Capabilities

### New Capabilities

- `setup-wizard`: 4-branch menu, API URL always prompted, workspace resolution (local path or git clone)
- `api-url-config`: `api_base_url` persistence, migration from `api_port`, serve bind from parsed URL

### Modified Capabilities

- `agent-skill`: Interactive agent picker; skill updated every setup (not `--agent`-gated)
- `embed-providers`: Setup sequence starts with API URL + branch; blank API key behavior
- `cli-and-serve`: Setup delegates to `scout/setup/runner`; serve uses configured host

## Impact

- `scout/config.py` — `api_base_url` field
- `scout/cli/main.py` — thinner setup/serve
- `scout/setup/*` — new module
- Tests, README, journal, memory cards
