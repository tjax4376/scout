# Scout v2

Local code-graph + vector search for coding agents.

Pipeline: folder scan → AST parse → in-memory petgraph → sqlite-vec embeddings → REST search with graph neighbors.

## Quick start

```bash
scout myapp setup --agent cursor
scout myapp search "authentication handler"
scout serve
```

## CLI reference

**Shape:** `<space>` first, then command. Agent is a flag, not a positional arg.

```
scout <space> setup   [--agent cursor|pi|opencode] [--force]
scout <space> reindex [--force]
scout <space> search  <query> [--top-k N]
scout serve
scout stop-serve
```

| Command | Example |
|---------|---------|
| Setup + Cursor skill | `scout myapp setup --agent cursor` |
| Setup, project skill only | `scout myapp setup --agent cursor` (pick `project` at prompt) |
| Reindex | `scout myapp reindex` |
| Reindex, bypass byte cap | `scout myapp reindex --force` |
| Search (no serve needed) | `scout myapp search "auth handler"` |
| Search, limit results | `scout myapp search "handler" --top-k 5` |
| Start API for agents | `scout serve` |
| Stop API server | `scout stop-serve` |

**Common mistake:**

```bash
scout cursor setup    # wrong — "cursor" parsed as space name
scout myapp setup --agent cursor   # correct
```

`scout` with no args prints usage. `scout --help` same.

See `scope/scout-simple-mvp1.md` for full MVP1 requirements.

## Dev setup

Python 3.11+ required. Python 3.14 needs `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` at build time (abi3 wheels target 3.11+).

```bash
# Clone and enter repo
cd scout

# Virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Python deps + maturin
pip install maturin pytest pytest-asyncio httpx pyyaml rich typer fastapi uvicorn pydantic

# Build Rust extension (scout_core) into venv
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release

# Verify
python -c "import scout_core; print(scout_core.py_core_version())"
pytest -q
scout
```

Run before committing OpenSpec edits (also runs in CI):

```bash
scripts/scout.sh validate
# or: make validate-openspec
# or: python scripts/validate_openspec.py
```

Checks change artifacts under `openspec/changes/`, requirements/scenario sections, relative cross-ref links, **api-contracts.md** ↔ **rest-api/spec.md**, and **scout/api/app.py** route decorators.

### Interactive setup (4-branch wizard)

```bash
scout myapp setup
# or non-interactive agent: scout myapp setup --agent cursor
```

Every setup run:

1. **Scout API base URL** — full URL e.g. `http://127.0.0.1:8741/v1` (LAN IP supported; warns if non-loopback)
2. **Branch** — pick one of four paths:

| Branch | Files | Embed |
|--------|-------|-------|
| 1 | Local path | Local LLM (lmstudio / omlx / unsloth-studio) |
| 2 | Local path | OpenRouter |
| 3 | Git clone → cwd subdir | Local LLM |
| 4 | Git clone → cwd subdir | OpenRouter |

3. Workspace resolution (local root or `git clone --depth 1`)
4. Embed provider + model (API key prompt offers **leave blank to keep** if key exists)
5. Prescan → index
6. Agent selection (cursor / pi / opencode) + skill install with injected `scout_api`

`--agent` skips agent prompt for CI. Skill install runs every successful setup.

### Search without serve (pyo3 direct)

```bash
scout myapp search "error handling"
```

### API (for agents)

```bash
scout serve
scout stop-serve   # from another terminal
# POST http://127.0.0.1:8741/v1/spaces/myapp/search
```

## Project layout

```
scout_core/          # Rust engine (pyo3)
scout/               # Python CLI, API, embed, prescan, skill, setup
skills/search_scout/ # Agent skill template
openspec/            # Change specs and tasks (validate: scripts/scout.sh validate)
scripts/             # scout.sh build/start/validate, verify_pipx_install.sh
```

## Remaining tasks (MVP1)

All 88 MVP1 tasks complete. Archive with `/opsx:archive scout-simple-mvp1`.

## Distribution

Install (after PyPI release):

```bash
pipx install scout
```

Publish flow (maintainers):

1. Configure PyPI trusted publisher for `Publish` workflow, **or** set repo secret `PYPI_API_TOKEN`
2. Tag release: `git tag v0.1.0 && git push origin v0.1.0`
3. GitHub Actions `.github/workflows/publish.yml` builds multi-platform wheels (bundled `scout_core`) + sdist, uploads to PyPI

Verify local wheel + pipx (clean-machine simulation):

```bash
bash scripts/verify_pipx_install.sh
```

CI builds wheels on every push/PR (`.github/workflows/ci.yml`).
