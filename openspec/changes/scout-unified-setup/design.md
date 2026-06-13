## Context

MVP1 shipped interactive setup but hardcodes `127.0.0.1` for API URL and skill injection. Users need configurable base URL (LAN IP, custom port) and four setup paths without separate scripts.

## Goals / Non-Goals

**Goals:**
- One `scout <space> setup` entry with branch menu
- Full API base URL prompt every run
- Git clone to cwd subdirectory for remote repos
- Skill always installed with current URL

**Non-Goals:**
- Chat LLM configuration
- Remote indexing (index always runs on dev machine)
- Standalone `scout skill install` command

## Decisions

**Decision:** Store canonical `api_base_url` in `config.yaml`; derive `api_port` on save for backward compat.

**Decision:** Parse URL for `scout serve` bind host/port. Warn when host != `127.0.0.1` (LAN exposure).

**Decision:** `scout/setup/` module — api_url, workspace, prompts, embed, runner — keeps CLI thin and testable.

**Decision:** Git clone `--depth 1` to `Path.cwd() / subdir`. Validate URL scheme and subdir name.

**Decision:** `--agent` flag remains as non-interactive override for CI; default is interactive picker.

## Migration

On config load: if `api_base_url` missing, synthesize `http://127.0.0.1:{api_port}/v1`.

## Risks / Mitigations

| Risk | Mitigation |
|------|------------|
| Non-loopback serve exposes API | Warning at setup when host != 127.0.0.1 |
| Git URL injection | Scheme whitelist; no shell metacharacters in subdir |
| Port busy on custom host | Scan port..port+58 on that host |
