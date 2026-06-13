# Grill Outcome — Scout v2 Simple MVP1

**Source:** scout-simple-mvp1.md (original plan below)
**Date:** 2026-06-12
**Status:** Grill closed (pass 1: Q1–Q17, pass 2: Q18–Q35) — proceed to OpenSpec proposal

## Context

Scout v2 — generic code-graph + vector search for coding agents. Pipeline: folder scan → AST parse → in-memory graph (Rust/petgraph) → structure cached on disk + text/embeddings in sqlite-vec → REST search API. CLI `scout <space> setup`. No telemetry. `.scout/cache` for graph prefetch. Consumers: `search_scout` skill (Cursor / Pi / OpenCode).

**Revised architecture (post-grill):**

```
[Python: CLI + FastAPI + embed HTTP clients]
   ↓ pyo3
[Rust scout-core: scan, tree-sitter, petgraph, sqlite-vec, search]
   ↓
[.scout/cache/<space>/graph.bin]  +  [.scout/spaces/<space>/index.db]
```

---

## Decisions

| # | Question | Decision | Resolved |
|---|----------|----------|----------|
| Q1 | Scout v2 vs aiScout Cavern Scout | **Separate module** (`scout/`). Own binary + REST API. Cavern Scout stays in core. MVP1: no coupling. | yes |
| Q2 | Graph + vector store | **In-memory reduced relationship graph** (petgraph) + **sqlite-vec** for embedded code details. Neo4j dropped (license + footprint). | yes |
| Q2b | Data split | **Structure in-memory** (paths, symbols, edges — no body text). **Text + vectors in sqlite-vec**. `node_id` links layers. No duplicate call graph in vector store. | yes |
| Q3 | Embeddings | **Separate embed config from chat LLM**. **Local-first** via generic provider registry (not Ollama-specific). Remote API fallback. Same model for index + query. | yes |
| Q4 | Chunk granularity | **Symbol-first**, file fallback, oversized symbols split (~512–1k tokens, 64 overlap). | yes |
| Q5 | `space` semantics | **Named workspace index** — alias → root path, isolated state per space under `.scout/`. | yes |
| Q6 | Language support | **TS/JS, Python, Rust, Go** full AST (tree-sitter). Configs/docs file-only. Standard skip dirs. Parse fail → file chunk. | yes |
| Q7 | Deployment | **All local dev workstation**, same machine as coding agent. **No Docker**. | yes |
| Q7c | sqlite-vec schema | **One `index.db` per space** at `.scout/spaces/<name>/index.db`. `chunks` table: text + embedding + `node_id` → petgraph. `meta` table for schema/model version. | yes |
| Q8 | Search API | **localhost REST `/v1`**, OpenAPI spec. `POST .../search` + graph context. Skill → HTTP. **No webhook MVP1**. | yes |
| Q9 | Python/Rust split | **Rust `scout-core`**: scan, parse, graph, sqlite-vec, search. **Python**: CLI, FastAPI, embed providers, prescan orchestration. **pyo3** binding. | yes |
| Q10 | Reindex | **Full rebuild** on setup/reindex. Manifest staleness check. `X-Scout-Stale` header. No watch/incremental MVP1. | yes |
| Q11 | Secrets | **Split** `config.yaml` / `secrets.yaml`. Gitignore. `chmod 600` on secrets. Env override for CI. | yes |
| Q12 | Prescan | Metrics → table + `prescan.json`. **Warn + confirm**. Hard stop at user cap or **100GB**. `--force` override. | yes |
| Q13 | `node_id` | **Deterministic blake3** key: `space + rel_path + kind + symbol + start/end line` (trunc 16 hex). `X-Scout-Index-Version` header. | yes |
| Q14 | Non-goals | Explicit cut line — see below. | yes |
| Q15 | Distribution | **PyPI `scout` + maturin `scout_core` wheels**. `pipx install scout` primary. CI multi-platform. | yes |
| Q16 | `search_scout` skill | **Ship in repo**. Setup installs to agent skills dir. **User picks agent**: Cursor, Pi, OpenCode (MVP1). | yes |
| Q17 | Serve + ports | **Separate API port scan** (8741+) and **embed endpoint scan**. **`scout serve` manual foreground**. PID lock file. | yes |
| Q18 | Petgraph edge types | **Base:** `contains` (dir→file→symbol). **MVP2 (code review):** full file↔file, module↔module, loop→module, function↔function analysis. | yes |
| Q19 | Search response | **Include `neighbors`**. Traversal: **up 1 node, then down 3 nodes** from anchor. Add `imports`/`calls` edges in MVP1 **if required** for that traversal. | yes |
| Q20 | Neighbor traversal | **Option A — anchor pivot.** Hit = anchor. Up 1 via `contains` parent. Down 3 = BFS from pivot, depth ≤3, edges `contains`+`imports`+`calls`. Cap 20 nodes, dedupe, exclude anchor. | yes |
| Q21 | Search request | `query` required. Optional: `top_k` (10), `min_score` (0.0), `kinds[]`, `path_prefix`. No pagination. Vector-only. | yes |
| Q22 | Search response | Per-hit: metadata + `snippet` (~500 chars) + `breadcrumb` + nested `neighbors[]` (`edge`, `depth` 1–3). Top-level: `stale`, `index_version`. `GET /node/{id}` = full chunk, no score. | yes |
| Q23 | Embed providers | **Remote:** `openrouter` — API key in secrets; fetch models at setup, user picks embed model. **Local:** `lmstudio`, `omlx`, `unsloth-studio` — warn user: embedding/tool models only (not chat). Same model+dims for index + query. | yes |
| Q24 | Setup flow | Interactive: root → provider → auth/endpoint → fetch models → filter embed-capable → warn → pick → probe dims → prescan → index. Fail = abort, no partial index. Reindex on provider/model/dim change. | yes |
| Q25 | CLI vs serve | CLI (`setup\|reindex\|search`) = **pyo3 direct**, no serve required. `scout serve` = agent REST only. Skill → HTTP. CLI never auto-hops to HTTP even if serve running. | yes |
| Q26 | Staleness | `manifest.json`: per-file `mtime`+`size` + embed config. Check on search. New/deleted/changed files or embed mismatch → `stale: true` + header. **Still return results.** No fs watch. | yes |
| Q27 | Static resolution | `imports`: single unambiguous workspace file only. `calls`: same-file always; cross-file via import graph + exported name. No type inference, no dynamic/reflection. Unresolved = skip edge. | yes |
| Q28 | Skill install | Ship `skills/search_scout/` in repo. Setup `--agent cursor\|pi\|opencode`. **Offer global + project-level install** (user picks one or both). Inject `scout_api` + `default_space`. Overwrite only with `--force`. | yes |
| Q29 | pyo3 boundary | Rust: scan, parse, graph, sqlite-vec, vector search, neighbors, staleness, reindex storage. Python: CLI, FastAPI, embed HTTP, prescan, config, skill install. Python embeds → passes `Vec<f32>` to Rust. Rust never holds keys. | yes |
| Q30 | Local endpoint discovery | Provider defaults (`lmstudio` 1234, `omlx` 8080, `unsloth-studio` 8000). **Setup prompts user for port range** (suggested default per provider). Scan `127.0.0.1` range → probe `GET /v1/models` → pick endpoint → store in config. Manual URL fallback. | yes |
| Q31 | Prescan + capacity | Filesystem walk → metrics table + `prescan.json`. Estimate disk (index+vectors) + RAM (index build). **Check available disk + RAM; proceed only if both ≥ estimated.** Else hard fail: `"not enough capacity"`. `--force` bypasses byte cap (100GB) only, not capacity gate. | yes |
| Q32 | Reindex | **Sync only — no background jobs ever.** Block until done. Atomic swap (temp → rename). 409 if reindex in progress. Long index time acceptable (token cost tradeoff). CLI + API same path. | yes |
| Q33 | Multi-space serve | **One `scout serve`** for all spaces in `config.yaml`. Single port + PID. Routes `/v1/spaces/{space}/...`. Unknown space → 404. Isolated state per space. | yes |
| Q34 | Skip rules | Hardcoded: `.git`, `node_modules`, `target`, `dist`, `build`, `__pycache__`, `.venv`, `vendor`, `.scout`, `.cursor`, caches, minified assets. Space config optional `skip.globs` + `skip.paths`. Binary → skip. No `.gitignore` MVP1. | yes |
| Q35 | Node kinds | `directory`, `file`, `module`, `class`, `struct`, `interface`, `enum`, `function`, `method`, `const`. `kinds[]` filter matches exactly. Parse fail → `file`. | yes |

**Skill paths (Q28 detail):**

| Agent | Global | Project (workspace root) |
|-------|--------|--------------------------|
| Cursor | `~/.cursor/skills/search_scout/` | `<root>/.cursor/skills/search_scout/` |
| Pi | `~/.pi/skills/search_scout/` | `<root>/.pi/skills/search_scout/` |
| OpenCode | `~/.config/opencode/skills/search_scout/` | `<root>/.opencode/skills/search_scout/` |

Setup prompt: *global / project / both*. Same template; port + space injected per target.

---

## MVP1 Ships

- `scout <space> setup|reindex|serve|search` CLI
- Named spaces, local workstation only
- Rust engine: scan, 4-lang AST, petgraph, sqlite-vec
- Python: FastAPI REST, generic local-first embed providers + remote fallback, prescan
- `.scout/cache/<space>/graph.bin`, `.scout/spaces/<space>/index.db`, manifest staleness
- `search_scout` skill for Cursor / Pi / OpenCode (user picks at setup)
- No telemetry

## MVP1 Non-Goals

| Area | Deferred |
|------|----------|
| Neo4j / Docker | Dropped — sqlite-vec replaces |
| Cavern Scout bridge | No coupling to aiScout FTS/cards/specs |
| Webhook callbacks | REST pull only |
| Incremental index / fs watch | Full rebuild only |
| Chat LLM features | Code review, spec search, bug find, PII anon |
| Network scouts | Federation, remote instances |
| Languages beyond TS/JS, Py, Rust, Go | File-only fallback only |
| OS keychain secrets | File + env only |
| Async reindex jobs | Sync only — **no background jobs ever** |
| Hybrid FTS search | Vector-only (FTS5 stretch, not committed) |
| Auth on API | localhost bind sufficient |
| Cloud deploy / CI index service | Dev workstation module only |
| Graphify | Replaced by `scout-core` |
| Auto-daemon / systemd | Manual `scout serve` |

---

## Key API Surface

```
GET  /v1/health
POST /v1/spaces/{space}/search   # results + neighbors (up 1, down 3)
GET  /v1/spaces/{space}/node/{node_id}
POST /v1/spaces/{space}/reindex
```

Response headers: `X-Scout-Stale`, `X-Scout-Index-Version`

---

## Config Layout

```
.scout/
  config.yaml          # ports, spaces, embed provider/model/endpoint (no secrets)
  secrets.yaml         # openrouter_api_key, chmod 600
  scout.pid            # serve lock
  cache/<space>/graph.bin
  spaces/<space>/
    config.yaml        # workspace root
    index.db           # sqlite-vec
    manifest.json      # staleness
    prescan.json       # prescan metrics
```

```yaml
# config.yaml — embed section
embed:
  provider: openrouter          # openrouter | lmstudio | omlx | unsloth-studio
  model: <selected at setup>
  endpoint: http://127.0.0.1:1234/v1   # local providers only; port scan at setup
  dimensions: 768                     # probed at setup, stored in meta
```

```yaml
# secrets.yaml (chmod 600)
openrouter_api_key: sk-or-...
```

---

## Summary

Grill resolved 35 decisions (17 pass 1 + 18 pass 2). Major pivot: **Neo4j → sqlite-vec** (license, footprint, no Docker/server). Architecture: **Rust engine + Python shell via pyo3**, **split in-memory graph / vector store**, **OpenRouter + local embed providers**, **named spaces**, **sync full rebuild indexing (no background jobs ever)**, **REST + agent skill** for Cursor/Pi/OpenCode. Ready for OpenSpec proposal and requirement block.

---

## Original Plan (reference)

# Scout v2 - generic search for Coding Agent
This will build a vectorDB of your files, relationships and group them heurstically.

Use case:
- Perfect for code-review agents without loading into frontier model and wasting tokens

scout <space> setup - {collects provider/model / api key & scans local ports in case local LLM is

[scout] --> {feeds dev stack + folder structure, searches folders for stack based file types, sending this to be graphed} --> {Graphify clone is used to parse files, creates relationshops and generates a graph, including cached version} --> {graph is sent to VectorDB is full umbedding is required} --> {index is built} --> {scout serves an API to search the graph}

{Code-agent} uses either webhook or free search_scout skill

| Component      | worth moving to rust? |
|----------------|-----------------------|
| file scanning  | minor gain            |
| parsing (AST)  | yes                   |
| Graph building | high impact           |
| Traversals     | major win             |
| LLM Calls      | keep in python        |

## Must Have (original)
- api contracts to support agent --> scout search requests
- agent setup, based on provider/model to ensure hooks to scout are documented
- use of folder .scout/cache for prefech of existing graphs to speed up vectordb creation
- a lightweight python binary {limited libraries} and rust binary bound together
- prescan of folders, before parsing an propose potential VRAM/RAM usage
- ability to add provider, model and store api key within local file
- a port scanner to locate an unused local network port for scout's api
- No telemetry. period.

## Nice to have (original — all deferred)
- perform code-reviews
- assist with spec searches,
- create patterns using working code
- Idenfity bugs and propose solutions in a spec
- anonamize PII
- talk to other scout's on the network
- talk with local or remote llm models
