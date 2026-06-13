## Context

Scout v2 is a new standalone module for local code-graph + vector search on developer workstations. Coding agents (Cursor, Pi, OpenCode) need symbol-level search with structural context without loading entire repos into LLM context. Grill session resolved 35 decisions: Neo4j dropped (license + footprint), replaced by in-memory petgraph + sqlite-vec; Rust engine for scan/parse/graph/search; Python for CLI, API, and embed HTTP; pyo3 binding; sync full-rebuild indexing only.

**Current state:** Greenfield — no existing `scout/` codebase. Scope document at `scope/scout-simple-mvp1.md` is the authoritative decision record.

**Constraints:**
- All local dev workstation; no Docker, no cloud deploy, no telemetry
- REST API localhost only; no auth MVP1
- No coupling to Cavern Scout / aiScout core
- No background jobs ever — sync reindex blocks until done
- Embed keys stay in Python; Rust never holds secrets
- Modules deployable independently; integrations via REST only (per project principles)

## Goals / Non-Goals

**Goals:**
- Index workspace code (TS/JS, Python, Rust, Go) into structure graph + vector store per named space
- Expose vector search with graph neighbor context (anchor pivot: up 1, down 3)
- Provide CLI for setup/reindex/search and optional `scout serve` for agent HTTP access
- Support local-first embed providers with OpenRouter remote fallback
- Ship `search_scout` skill for Cursor, Pi, OpenCode
- Prescan with capacity gate before indexing
- Detect staleness via manifest; still return results when stale

**Non-Goals:**
- Neo4j, Docker, federation, webhooks
- Incremental index, fs watch, async background reindex
- Chat LLM features (code review, spec search, PII anon)
- Hybrid FTS search (vector-only MVP1)
- Auth on API, OS keychain, cloud CI index service
- Languages beyond TS/JS, Python, Rust, Go (file-only fallback for others)
- Cavern Scout bridge, Graphify reuse
- Auto-daemon / systemd

## Decisions

### 1. Rust engine + Python shell via pyo3

**Decision:** Rust `scout-core` owns scan, tree-sitter parse, petgraph build, sqlite-vec read/write, vector search, neighbor traversal, staleness check, reindex storage. Python owns CLI, FastAPI, embed HTTP clients, prescan orchestration, config, skill install. Python embeds text → passes `Vec<f32>` to Rust.

**Rationale:** AST parsing, graph traversal, and vector search are CPU-bound; Rust gives major wins. LLM/embed HTTP calls are I/O-bound and provider-specific; Python is simpler for CLI/API ergonomics and rapid provider iteration.

**Alternatives considered:**
- All-Python: rejected — graph traversal and parsing too slow at scale
- All-Rust: rejected — embed provider diversity and CLI UX favor Python
- Separate processes via REST only: rejected for CLI path — pyo3 direct calls avoid serve dependency

### 2. Split data layer: petgraph (structure) + sqlite-vec (text + vectors)

**Decision:** In-memory petgraph holds paths, symbols, edges — no body text. sqlite-vec `chunks` table holds text + embedding + `node_id` linking to graph. Graph serialized to `.scout/cache/<space>/graph.bin`. One `index.db` per space at `.scout/spaces/<space>/index.db`.

**Rationale:** Structure queries and neighbor traversal are graph-native; duplicating call graph in vector store wastes space. sqlite-vec avoids Neo4j license and server footprint.

**Alternatives considered:**
- Neo4j: dropped — license, Docker, operational overhead
- All-in-sqlite: rejected — graph traversal performance and flexibility favor petgraph in memory

### 3. Deterministic node_id via blake3

**Decision:** `node_id` = blake3 hash of `space + rel_path + kind + symbol + start_line + end_line`, truncated to 16 hex chars. `X-Scout-Index-Version` header on API responses.

**Rationale:** Stable IDs across reindex enable cache reuse and agent bookmarking. blake3 is fast and collision-resistant at 16 hex for workspace scale.

### 4. Symbol-first chunking with file fallback

**Decision:** Parse AST → chunk per symbol. Oversized symbols split at ~512–1k tokens with 64-token overlap. Parse fail → single `file` chunk. Node kinds: `directory`, `file`, `module`, `class`, `struct`, `interface`, `enum`, `function`, `method`, `const`.

**Rationale:** Symbol granularity matches agent lookup patterns. File fallback ensures coverage for unsupported languages and parse failures.

### 5. Graph edges MVP1: contains + imports + calls

**Decision:** Base edge `contains` (dir→file→symbol). Add `imports` and `calls` where statically resolvable. `imports`: single unambiguous workspace file only. `calls`: same-file always; cross-file via import graph + exported name. Unresolved = skip edge. Full cross-entity analysis deferred to MVP2.

**Rationale:** Neighbor traversal (up 1, down 3) needs `contains` parent chain; `imports`/`calls` enrich down-traversal context for code review use case.

### 6. Neighbor traversal: anchor pivot

**Decision:** Search hit = anchor. Up 1 via `contains` parent. Down 3 = BFS from pivot (not anchor), depth ≤3, edges `contains`+`imports`+`calls`. Cap 20 neighbor nodes, dedupe, exclude anchor. Per-neighbor: `edge`, `depth` (1–3).

**Rationale:** Anchor gives semantic match; pivot (parent) gives file/module context; down-traversal surfaces related symbols.

### 7. Embed provider registry (Python-only)

**Decision:** Providers: `openrouter` (remote, API key in secrets.yaml), `lmstudio`, `omlx`, `unsloth-studio` (local, port scan at setup). Setup: interactive flow probes dims, stores in config. Same model+dims for index and query. Reindex required on provider/model/dim change.

**Rationale:** Local-first reduces cost and latency; OpenRouter fallback for users without local embed models. Generic registry avoids Ollama lock-in.

### 8. Sync full reindex with atomic swap

**Decision:** `setup` and `reindex` do full rebuild. Write to temp paths → atomic rename on success. 409 if reindex already in progress. Manifest records per-file mtime+size + embed config. No partial index on failure.

**Rationale:** Simplicity for MVP1; incremental deferred. Atomic swap prevents corrupted half-built index.

### 9. CLI direct pyo3; serve for agents only

**Decision:** `scout <space> setup|reindex|search` call Rust via pyo3 directly — never auto-hop to HTTP even if serve running. `scout serve` binds localhost, one instance for all spaces, routes `/v1/spaces/{space}/...`. PID lock at `.scout/scout.pid`. Port scan from 8741.

**Rationale:** CLI works without daemon; agents use HTTP via skill. Separation prevents hidden dependencies.

### 10. Distribution: PyPI + maturin wheels

**Decision:** `pipx install scout` primary install path. Package `scout` (Python) + `scout_core` (maturin Rust wheels). CI multi-platform wheel build.

**Rationale:** Standard Python distribution; maturin handles pyo3 binary packaging cross-platform.

### 11. Module layout

**Decision:**
```
scout/
  scout_core/          # Rust crate (pyo3 module)
    src/
      scan.rs
      parse/           # tree-sitter per language
      graph.rs         # petgraph build + serialize
      index.rs         # sqlite-vec read/write
      search.rs        # vector search + neighbors
      staleness.rs
  scout/               # Python package
    cli/
    api/               # FastAPI
    embed/             # provider registry
    prescan/
    skill/
  skills/search_scout/
```

**Rationale:** Clear pyo3 boundary; each subdirectory is independently testable module per project principles.

## Risks / Trade-offs

- **[Risk] Large repo index time** → Acceptable tradeoff for MVP1 (token cost vs index time). Prescan warns user. Sync blocking is explicit.
- **[Risk] Static import/call resolution incomplete** → Unresolved edges skipped; search still works via vector similarity. MVP2 adds deeper analysis.
- **[Risk] Embed model mismatch between index and query** → Config stores model+dims; manifest tracks embed config; staleness flag on mismatch. Reindex required on change.
- **[Risk] Local embed endpoint unavailable** → Setup probes and stores endpoint; serve/CLI fail clearly if endpoint down at index time.
- **[Risk] pyo3 cross-platform wheel build complexity** → CI multi-platform from day one; maturin standard tooling mitigates.
- **[Risk] RAM pressure on large graphs** → Prescan estimates RAM; capacity gate blocks if insufficient. graph.bin enables reload without rebuild.
- **[Trade-off] No incremental index** → Full rebuild on every reindex. Simpler correctness; slower for large repos.
- **[Trade-off] Vector-only search** → No keyword/FTS fallback. May miss exact identifier matches not semantically similar.
- **[Trade-off] No API auth** → Localhost bind only. Sufficient for dev workstation; not suitable for network exposure.

## Migration Plan

Greenfield — no migration from existing systems.

**Deploy steps:**
1. `pipx install scout`
2. `scout <space> setup` — interactive provider/space/root config
3. Optional: `scout serve` for agent HTTP access
4. Agent skill installed during setup (global and/or project)

**Rollback:** Delete `.scout/` directory and uninstall package. No external state.

## Open Questions

- Exact token counting library for chunk splitting (tiktoken vs provider-specific) — decide at implementation; must be consistent across reindex
- tree-sitter grammar versions to pin per language — pin in Cargo.toml at implementation
- CI pipeline structure for multi-platform wheel + PyPI publish — define in tasks; must be single integrated pipeline per project principles
