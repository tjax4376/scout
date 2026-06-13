## Why

Coding agents waste tokens loading entire codebases into frontier models for tasks like code review and symbol lookup. Scout v2 MVP1 delivers a local, generic code-graph + vector search module that indexes workspace structure and embeddings on the developer workstation, exposing REST search with graph context so agents can query precisely without full-repo context. Grill closed 35 decisions; Neo4j dropped in favor of sqlite-vec + in-memory petgraph for license, footprint, and zero-Docker local dev.

## What Changes

- New standalone `scout/` module (separate from Cavern Scout / aiScout core) with PyPI distribution (`pipx install scout`)
- Rust `scout-core` engine via pyo3: folder scan, tree-sitter AST (TS/JS, Python, Rust, Go), petgraph relationship graph, sqlite-vec vector store, neighbor traversal, staleness checks
- Python shell: CLI (`setup`, `reindex`, `search`, `serve`), FastAPI REST API, embed provider HTTP clients, prescan orchestration, skill install
- Named workspace spaces with isolated state under `.scout/` (config, secrets, cache, index per space)
- Local-first embed providers (lmstudio, omlx, unsloth-studio) + OpenRouter remote fallback; separate embed config from chat LLM
- Sync full-rebuild indexing only — no background jobs, no incremental watch, no fs watch
- `search_scout` agent skill for Cursor, Pi, and OpenCode (user picks at setup; global and/or project install)
- Prescan with disk + RAM capacity gate before indexing; hard stop at user cap or 100GB (unless `--force`)
- REST API on localhost (`/v1`) with search + graph neighbors (anchor pivot: up 1, down 3), node lookup, reindex
- No telemetry, no auth (localhost bind), no Docker, no Neo4j, no Cavern Scout coupling

## Capabilities

### New Capabilities

- `code-indexing`: File scan, skip rules, tree-sitter AST parsing, symbol-first chunking, petgraph graph build (`contains`, `imports`, `calls` edges), deterministic `node_id`, sqlite-vec storage, graph.bin cache, manifest staleness, sync full reindex with atomic swap
- `vector-search`: Vector-only search with `query`, `top_k`, `min_score`, `kinds[]`, `path_prefix` filters; neighbor traversal via anchor pivot (up 1 via `contains`, down 3 BFS, cap 20); per-hit metadata, snippet, breadcrumb, nested neighbors; staleness surfaced in response
- `rest-api`: FastAPI localhost REST at `/v1` — health, per-space search, node lookup, reindex; multi-space routing; `X-Scout-Stale` and `X-Scout-Index-Version` headers; OpenAPI spec; 409 on concurrent reindex
- `cli-and-serve`: Python CLI commands (`scout <space> setup|reindex|search|serve`); pyo3 direct calls for CLI (no HTTP hop); `scout serve` manual foreground with PID lock and port scan from 8741; one serve instance for all spaces
- `embed-providers`: Provider registry (openrouter, lmstudio, omlx, unsloth-studio); interactive setup flow (root → provider → auth/endpoint → model pick → dim probe); split config/secrets; local port-range scan; same model+dims for index and query; Python-only embed (Rust receives `Vec<f32>`)
- `prescan`: Filesystem walk metrics table + `prescan.json`; disk and RAM estimate; capacity gate (both must exceed estimate); warn + confirm; `--force` bypasses byte cap only
- `space-config`: Named spaces (alias → root path); `.scout/` layout (config.yaml, secrets.yaml, cache, spaces); per-space config, index.db, manifest; multi-space serve routing; env override for CI secrets
- `agent-skill`: Ship `skills/search_scout/` in repo; setup installs to agent-specific paths (Cursor / Pi / OpenCode); global and/or project-level; inject `scout_api` + `default_space`; overwrite only with `--force`

### Modified Capabilities

<!-- No existing specs in openspec/specs/ — all capabilities are new -->

## Impact

- **New codebase**: `scout/` module with Rust `scout-core` crate and Python package bound via maturin/pyo3
- **Dependencies**: tree-sitter (4 languages), petgraph, sqlite-vec, blake3, FastAPI, pyo3, maturin; embed HTTP clients per provider
- **Distribution**: PyPI `scout` + multi-platform `scout_core` wheels; CI multi-platform build
- **Local filesystem**: `.scout/` directory tree per user machine; `chmod 600` on secrets.yaml
- **Agent integration**: `search_scout` skill installed to Cursor/Pi/OpenCode skills directories
- **No impact on**: Cavern Scout / aiScout core (explicit non-goal — no coupling MVP1)
