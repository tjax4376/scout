## 1. Project Scaffolding

- [ ] 1.1 Create `scout/scout_core/` Rust crate with pyo3, maturin, and workspace Cargo.toml
- [ ] 1.2 Create `scout/scout/` Python package with pyproject.toml, CLI entry point, and FastAPI dependency
- [ ] 1.3 Configure maturin build linking `scout_core` as Python module; verify `maturin develop` imports on dev machine
- [ ] 1.4 Add tree-sitter grammars (TS/JS, Python, Rust, Go), petgraph, blake3, sqlite-vec to Rust dependencies
- [ ] 1.5 Create module directory layout per design: `cli/`, `api/`, `embed/`, `prescan/`, `skill/`, `src/scan.rs`, `parse/`, `graph.rs`, `index.rs`, `search.rs`, `staleness.rs`

## 2. Space Config and Storage

- [ ] 2.1 Implement `.scout/` directory bootstrap (create config.yaml, secrets.yaml templates)
- [ ] 2.2 Implement named space registry in config.yaml (alias → root path)
- [ ] 2.3 Implement per-space storage paths: `spaces/<space>/config.yaml`, `index.db`, `manifest.json`, `prescan.json`, `cache/<space>/graph.bin`
- [ ] 2.4 Implement secrets.yaml write with chmod 600 and env var override support (`OPENROUTER_API_KEY`)
- [ ] 2.5 Implement config validation: space exists, root path valid, embed config present

## 3. File Scan (scout-core)

- [ ] 3.1 Implement recursive filesystem walk from workspace root
- [ ] 3.2 Implement hardcoded skip directories (`.git`, `node_modules`, `target`, `dist`, `build`, `__pycache__`, `.venv`, `vendor`, `.scout`, `.cursor`, caches)
- [ ] 3.3 Implement per-space `skip.globs` and `skip.paths` from space config
- [ ] 3.4 Implement binary file detection and skip
- [ ] 3.5 Expose scan results (file paths, sizes, mtimes) via pyo3 for prescan and indexing

## 4. AST Parsing (scout-core)

- [ ] 4.1 Implement tree-sitter parser module with language dispatch (TS/JS, Python, Rust, Go)
- [ ] 4.2 Implement symbol extraction per language (functions, classes, structs, interfaces, enums, methods, modules, consts)
- [ ] 4.3 Implement node kind assignment per Q35 spec
- [ ] 4.4 Implement parse-failure fallback to single `file` kind node
- [ ] 4.5 Implement config/doc file detection for file-only indexing (no AST)

## 5. Chunking (scout-core)

- [ ] 5.1 Implement symbol-first chunking (one chunk per symbol)
- [ ] 5.2 Implement oversized symbol splitting (~512–1024 tokens, 64-token overlap)
- [ ] 5.3 Implement deterministic `node_id` generation (blake3 of space + rel_path + kind + symbol + start/end line, truncate 16 hex)

## 6. Graph Building (scout-core)

- [ ] 6.1 Implement petgraph graph builder with `directory`, `file`, and symbol nodes
- [ ] 6.2 Implement `contains` edges (dir → file → symbol)
- [ ] 6.3 Implement static `imports` edge resolution (single unambiguous workspace file only)
- [ ] 6.4 Implement static `calls` edge resolution (same-file always; cross-file via import graph + exported name)
- [ ] 6.5 Implement graph.bin serialization and deserialization to `.scout/cache/<space>/graph.bin`

## 7. Vector Store (scout-core)

- [ ] 7.1 Implement sqlite-vec database creation per space at `.scout/spaces/<space>/index.db`
- [ ] 7.2 Implement `chunks` table (text, embedding vector, node_id) and `meta` table (schema version, model, dimensions)
- [ ] 7.3 Implement batch embedding insert from Python-provided `Vec<f32>` via pyo3
- [ ] 7.4 Implement vector similarity search with top_k and min_score filtering
- [ ] 7.5 Implement kind and path_prefix filtering on search results

## 8. Embed Providers (Python)

- [ ] 8.1 Implement provider registry with adapters for openrouter, lmstudio, omlx, unsloth-studio
- [ ] 8.2 Implement OpenRouter model fetch and embed-capable model filtering
- [ ] 8.3 Implement local provider port-range scan on 127.0.0.1 with `GET /v1/models` probe
- [ ] 8.4 Implement default port suggestions per provider (lmstudio 1234, omlx 8080, unsloth-studio 8000) with user override
- [ ] 8.5 Implement embed dimension probing and storage in config + meta table
- [ ] 8.6 Implement embedding call returning `Vec<f32>` for batch index and single query paths
- [ ] 8.7 Implement local provider warning (embedding/tool models only, not chat)

## 9. Prescan (Python)

- [ ] 9.1 Implement prescan orchestration using scout-core scan results
- [ ] 9.2 Implement metrics table display (file count, total bytes, language breakdown)
- [ ] 9.3 Implement disk and RAM usage estimation
- [ ] 9.4 Implement capacity gate (available disk ≥ estimate AND available RAM ≥ estimate; else hard-fail "not enough capacity")
- [ ] 9.5 Implement byte cap enforcement (user cap or 100GB) with `--force` override (capacity gate not bypassed)
- [ ] 9.6 Implement user confirmation prompt and prescan.json write

## 10. Search and Neighbors (scout-core)

- [ ] 10.1 Implement vector search orchestration (query embed from Python → search in Rust)
- [ ] 10.2 Implement search hit formatting (metadata, ~500 char snippet, breadcrumb)
- [ ] 10.3 Implement neighbor traversal: anchor pivot, up 1 via `contains`, down 3 BFS via `contains`+`imports`+`calls`
- [ ] 10.4 Implement neighbor cap (20 nodes), deduplication, anchor exclusion
- [ ] 10.5 Implement `GET /node/{id}` full chunk retrieval without score

## 11. Staleness and Reindex (scout-core + Python)

- [ ] 11.1 Implement manifest.json write (per-file mtime+size, embed config)
- [ ] 11.2 Implement staleness check on search (filesystem diff + embed config mismatch)
- [ ] 11.3 Implement sync full reindex with temp write → atomic rename
- [ ] 11.4 Implement reindex-in-progress lock with 409 on concurrent request
- [ ] 11.5 Implement index_version generation and `X-Scout-Index-Version` header value

## 12. pyo3 Bindings

- [ ] 12.1 Expose scan, parse, graph build, index write, search, neighbors, staleness, reindex as pyo3 functions
- [ ] 12.2 Define Python-Rust data transfer types (file metadata, graph nodes, search results, embeddings)
- [ ] 12.3 Verify CLI path works end-to-end via pyo3 without HTTP

## 13. CLI (Python)

- [ ] 13.1 Implement `scout <space> setup` interactive flow (root → provider → auth/endpoint → model → dims → prescan → index → skill install)
- [ ] 13.2 Implement `scout <space> reindex` (sync full rebuild via pyo3)
- [ ] 13.3 Implement `scout <space> search <query>` (pyo3 direct, formatted output)
- [ ] 13.4 Implement `scout serve` foreground process with PID lock at `.scout/scout.pid`
- [ ] 13.5 Implement API port scan from 8741 with config storage
- [ ] 13.6 Implement `--force` flag for setup/reindex (byte cap bypass only)
- [ ] 13.7 Implement `--agent cursor|pi|opencode` flag for skill install target

## 14. REST API (Python FastAPI)

- [ ] 14.1 Implement `GET /v1/health`
- [ ] 14.2 Implement `POST /v1/spaces/{space}/search` with request validation and response formatting
- [ ] 14.3 Implement `GET /v1/spaces/{space}/node/{node_id}`
- [ ] 14.4 Implement `POST /v1/spaces/{space}/reindex` with 409 on concurrent
- [ ] 14.5 Implement `X-Scout-Stale` and `X-Scout-Index-Version` response headers
- [ ] 14.6 Implement 404 for unknown space
- [ ] 14.7 Generate OpenAPI spec

## 15. Agent Skill

- [ ] 15.1 Create `skills/search_scout/` skill template with REST API usage docs
- [ ] 15.2 Implement skill install logic for Cursor, Pi, OpenCode paths (global and project)
- [ ] 15.3 Implement `scout_api` and `default_space` injection into installed skill
- [ ] 15.4 Implement overwrite protection (skip unless `--force`)

## 16. CI and Distribution

- [ ] 16.1 Configure CI pipeline for multi-platform maturin wheel build (Linux, macOS, Windows)
- [ ] 16.2 Configure PyPI publish for `scout` package with bundled `scout_core` wheels
- [ ] 16.3 Verify `pipx install scout` works on clean machine
- [ ] 16.4 Add `.gitignore` entries for `.scout/`, `secrets.yaml`, build artifacts

## 17. Integration Testing

- [ ] 17.1 Test end-to-end setup flow with mock local embed provider
- [ ] 17.2 Test search with neighbors on sample multi-file project (TS or Python)
- [ ] 17.3 Test staleness detection after file modification
- [ ] 17.4 Test reindex atomic swap and 409 concurrent guard
- [ ] 17.5 Test prescan capacity gate rejection
- [ ] 17.6 Test skill install to temp directories for each agent type
- [ ] 17.7 Test CLI search without serve running (pyo3 direct path)
