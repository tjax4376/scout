# Hawkeye — local graph-aware code reviewer

Deterministic code review for Scout: trace logging, SARIF findings, auth/API rule pack, hybrid AI escalation.

## Quick start

```bash
scout serve                    # terminal 1 — start Scout API
hawkeye setup                  # finds Scout on :8741-8799, picks space
hawkeye review --path src/auth/
hawkeye review --file scout/api/app.py
```

`hawkeye` is the first-class CLI (same as `python -m scout.hawkeye`).

**`command not found`?** Hawkeye installs into the project venv — activate it or use the wrapper:

```bash
source .venv/bin/activate   # from repo root after scripts/scout.sh build dev
hawkeye --help

# or without activate:
scripts/hawkeye.sh --help
./.venv/bin/hawkeye --help
python -m scout.hawkeye --help
```

## Setup

`hawkeye setup` discovers a running Scout API:

1. Scan `127.0.0.1:8741–8799` for `GET /v1/health`
2. Fall back to `.scout/config.yaml` (project or `~/.scout`)
3. List spaces via `GET /v1/spaces/list` and propose a default

```bash
hawkeye setup                  # interactive — proposes URL + space
hawkeye setup --yes --space myapp   # non-interactive CI
hawkeye setup --scout-api http://127.0.0.1:8741/v1 --space myapp

# project-local config
hawkeye setup --project --project-root .
```

If Scout is not running:

```bash
scout serve
hawkeye setup
```

Writes `~/.hawkeye/` or `.hawkeye/`:

- `config.yaml` — Scout API, space, trace dir (mode `0o600`)
- `rules.yaml` — v1 rule pack (10 auth/API rules)
- `antipatterns.yaml` — registered anti-patterns
- `traces/` — JSONL session logs

Built-in rule pack: `scout/hawkeye/rules/pack_v1/` (`rules.yaml`, `antipatterns.yaml`).

Override at review time:

```bash
hawkeye review --diff origin/main \
  --rules ./team-rules.yaml \
  --antipatterns ./pr-antipatterns.yaml
```

## Review backends

`hawkeye review --backend auto|graph|filesystem` (default `auto`):

| Backend | Scout | Symbols/neighbors | File reads |
|---------|-------|-------------------|------------|
| `graph` | Required | Scout REST API | Scout `/file` |
| `filesystem` | No | Skipped (empty) | Local disk |
| `auto` | Optional | Graph if Scout up, else filesystem | Per backend |

Filesystem mode skips `graph_neighbor` and `staleness_gate` rules (stderr + trace `skipped_rules`).

No `hawkeye setup` required for filesystem review — embedded rule pack + cwd `.hawkeye/traces`:

```bash
hawkeye review --backend filesystem --file src/main.py
hawkeye review --backend filesystem --path .
```

## Review scope

Exactly one scope mode per run:

| Mode | Flag | Example |
|------|------|---------|
| Git diff (default) | `--diff` | `hawkeye review --diff origin/main` |
| Directory | `--path` | `hawkeye review --path src/auth/` |
| Single file | `--file` | `hawkeye review --file scout/api/app.py` |

```bash
scout serve
hawkeye review --diff origin/main --sarif /tmp/hawkeye.sarif
hawkeye review --path scout/hawkeye/
hawkeye review --file scout/api/app.py
hawkeye review --backend filesystem --path .    # no Scout required
```

Exit codes for CI:

| Code | Meaning |
|------|---------|
| `0` | Success — no error-severity findings |
| `1` | Review completed with error-severity findings |
| `2` | Runtime failure (config, API, missing trace) |

Use `--advisory` to exit `0` when only warnings/info findings exist (runtime errors still exit `2`).

Hybrid mode (local first, agent handoff):

```bash
hawkeye review --diff origin/main --hybrid
# writes traces/<session>-escalation.json for unmapped hunks
```

## Other commands

```bash
hawkeye replay --session <uuid> --dry-run
hawkeye export-sarif --session <uuid> --output out.sarif
hawkeye mine --threshold 3 --limit 10 --offset 0
hawkeye promote --approve CAND-001
hawkeye feedback --session <uuid> --finding <id> --verdict accepted
```

## Scout API tracing

Hawkeye sends `X-Hawkeye-Session-Id` on all Scout calls.

Optional server-side trace logging on the Scout API process:

```bash
HAWKEYE_TRACE=1 scout serve
```

When enabled, Scout logs method, path, query, status, and session header for Hawkeye requests. Request/response bodies are not logged.

## Module boundary

Integrates with Scout via REST only (`/symbols`, `/neighbors`, `/file`). No shared in-process state with Scout core.

## Build and install

Hawkeye ships inside the `scout` Python package — no separate install.

```bash
# From repo root (dev)
scripts/scout.sh build dev       # verifies scout + hawkeye CLIs and rule pack
scripts/scout.sh test hawkeye    # Hawkeye tests only

# Standalone binary (PyInstaller one-file, no Python env required)
scripts/scout.sh build hawkeye-binary
# or: make build-hawkeye-binary
./dist/hawkeye --help
./dist/hawkeye review --backend filesystem --file src/main.py

# Wheel / pipx
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin build --release --out dist
pipx install dist/scout-*.whl
hawkeye --help

# Smoke verify
bash scripts/verify_pipx_install.sh
```

Packaged data: `scout/hawkeye/rules/pack_v1/*.yaml` (see `pyproject.toml` `[tool.setuptools.package-data]`).

Metadata: v1.3.0 | Scout Contributors | 2026-06-15
