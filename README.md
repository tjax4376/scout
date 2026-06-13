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

**Common mistake:**

```bash
scout cursor setup    # wrong — "cursor" parsed as space name
scout myapp setup --agent cursor   # correct
```

`scout` with no args prints usage. `scout --help` same.

See `scope/scout-simple-mvp1.md` for full MVP1 requirements.

## Dev setup

Python 3.11+ required. Python 3.14 needs ABI3 forward-compat flag at build time.

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

### Interactive setup

```bash
scout myapp setup --agent cursor
```

Flow: workspace root → embed provider → model pick → prescan → index → optional skill install.

### Search without serve (pyo3 direct)

```bash
scout myapp search "error handling"
```

### API (for agents)

```bash
scout serve
# POST http://127.0.0.1:8741/v1/spaces/myapp/search
```

## Project layout

```
scout_core/          # Rust engine (pyo3)
scout/               # Python CLI, API, embed, prescan, skill
skills/search_scout/ # Agent skill template
openspec/            # Change specs and tasks
```

## Remaining tasks (MVP1)

From `openspec/changes/scout-simple-mvp1/tasks.md` — 86/88 complete.

| Task | Description |
|------|-------------|
| 16.2 | Configure PyPI publish for `scout` package with bundled `scout_core` wheels |
| 16.3 | Verify `pipx install scout` works on clean machine |

All other MVP1 tasks are implemented. Archive change after distribution is done.

## Distribution (not yet wired)

Target install path:

```bash
pipx install scout
```

CI builds wheels on push (`.github/workflows/ci.yml`); PyPI publish step pending (task 16.2).
