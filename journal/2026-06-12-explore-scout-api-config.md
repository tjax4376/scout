# Scout API / config exploration

**Context:** Subagent exploration of REST API startup, port/config, skills, env vars, pyproject/scout_core entry points.

## Discussion points

1. How `scout serve` starts and binds
2. Health + API routes
3. Cursor skills referencing Scout API URL
4. Env vars for embed API keys
5. Python packaging and CLI entry points

## Summary

- **Serve:** `scout serve` → `uvicorn.run(create_app(), host="127.0.0.1", port=config.api_port)` in `scout/cli/main.py`
- **Port:** Default 8741; scanned 8741–8799 at setup via `find_free_api_port()`; stored in `.scout/config.yaml` as `api_port`
- **Health:** `GET /v1/health` → `{"status": "ok"}`
- **Base URL:** Not env-driven; computed as `http://127.0.0.1:{config.api_port}/v1` at setup skill install; injected into skill template as `{{SCOUT_API}}`
- **Skills:** Repo template `skills/search_scout/SKILL.md`; installed to `~/.cursor/skills/search_scout` or `{project}/.cursor/skills/search_scout` via `scout/skill/install.py`
- **Secrets env:** `OPENROUTER_API_KEY`, `LMSTUDIO_API_KEY`, `OMLX_API_KEY`, `UNSLOTH_STUDIO_API_KEY` override `secrets.yaml`
- **CLI entry:** `pyproject.toml` → `scout = "scout.cli.main:main"`
- **scout_core:** maturin extension module; pyo3 bindings in `scout_core/src/pyapi.rs`

## Code changed

None (read-only exploration).
