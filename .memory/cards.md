# Scout Memory Cards

## 2026-06-12 — Grill closed: Scout v2 MVP1 scope

**Issue:** Original plan ambiguous — Neo4j vs in-memory, module boundary, embed provider, agent integration. Pass 2 gaps: search contract, neighbor traversal, embed providers, pyo3 boundary, prescan capacity.

**Resolution (35 decisions):**
- Separate module from Cavern Scout; REST-only; no MVP1 coupling
- Neo4j dropped → **sqlite-vec** per space (license + footprint + no Docker)
- Structure: in-memory **petgraph** + `.scout/cache/graph.bin`
- Graph edges MVP1: `contains` + `imports`/`calls` (static, best-effort); full cross-entity analysis → MVP2
- Search: neighbors via anchor pivot (up 1, down 3, cap 20)
- Text/vectors: `.scout/spaces/<name>/index.db`
- Rust engine + Python CLI/API/embed via **pyo3**; embed stays Python-only
- Embed: **OpenRouter** + local **lmstudio/omlx/unsloth-studio**; user port range at setup
- Prescan: disk+RAM capacity gate; sync reindex only — **no background jobs ever**
- One `scout serve` for all spaces; skill install global + project-level
- Agent skill: user picks **Cursor / Pi / OpenCode** at setup
- `scout serve` manual foreground; port scan from 8741

**Ref:** `scope/scout-simple-mvp1.md`

## 2026-06-12 — MVP1 implementation (opsx-apply)

**Issue:** Greenfield build from OpenSpec tasks — 88 items across Rust core + Python shell.

**Resolution:**
- `scout_core` Rust engine compiles; pyo3 bindings exposed
- Python CLI/API/embed/prescan/skill implemented
- `maturin develop` works (Python 3.14 needs `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`)
- 8 pytest + 2 cargo tests pass
- **Distribution (2026-06-12):** PyPI publish workflow + abi3 wheels + `scripts/verify_pipx_install.sh`; 88/88 tasks complete

**Dev setup:**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install maturin pytest pytest-asyncio httpx pyyaml rich typer fastapi uvicorn
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release
pytest -q
```

**Local embed auth:** LM Studio etc may require API key. Setup prompts before model fetch; stored as `lmstudio_api_key` in `secrets.yaml`. Env: `LMSTUDIO_API_KEY`.

## 2026-06-12 — PyPI / pipx distribution

**Issue:** Tasks 16.2/16.3 pending — no publish workflow, no pipx verify.

**Resolution:**
- `.github/workflows/publish.yml` — tag `v*` → multi-platform wheels + sdist → PyPI (OIDC or `PYPI_API_TOKEN`)
- `py-limited-api` / abi3-py311 — cp311-abi3 wheels bundle `scout_core.so`
- `scripts/verify_pipx_install.sh` — temp PIPX_HOME install from wheel
- CI wheels: ubuntu + macos + windows matrix

**Publish:** `git tag v0.1.0 && git push origin v0.1.0`
**Verify:** `bash scripts/verify_pipx_install.sh`

## 2026-06-12 — Unified setup wizard (4-branch)

**Issue:** Setup hardcoded `127.0.0.1`; no git-clone branch; skill install gated on `--agent`; API key prompts unclear on re-setup.

**Resolution:**
- `scout <space> setup` wizard: API base URL → branch 1–4 → workspace → embed → index → agent → skill
- `api_base_url` in `config.yaml`; `scout serve` binds parsed host/port
- Git clone `--depth 1` to cwd subdirectory (branches 3–4)
- API key prompts: leave blank to keep existing key (shows stored model)
- Skill always installed with injected `scout_api`; `--agent` overrides picker for CI
- Module: `scout/setup/` (api_url, prompts, workspace, embed, runner)

**Setup branches:**
1. Local files + local LLM
2. Local files + OpenRouter
3. Git clone (cwd) + local LLM
4. Git clone (cwd) + OpenRouter

**Ref:** `openspec/changes/scout-unified-setup/`, `journal/2026-06-12-unified-setup.md`

## 2026-06-12 — scout stop-serve

**Issue:** No CLI to stop `scout serve`; users must manually find/kill PID.

**Resolution:**
- `scout stop-serve` reads `.scout/scout.pid`, SIGTERM → 5s wait → SIGKILL fallback
- Stale/missing PID: cleanup + friendly message, exit 0
- Module: `scout/serve/lifecycle.py`

**Ref:** `openspec/changes/scout-stop-serve/`

## 2026-06-12 — GET /v1/spaces/list

**Issue:** Agents need discover configured space names without reading config.yaml.

**Resolution:**
- `GET /v1/spaces/list` → `{spaces: [{name, root, skip_globs, skip_paths}]}` sorted by name
- No scout_core required; reads `load_config` only
- Tests: `tests/test_api.py`

**Ref:** `api-contracts.md`, `scout/api/app.py`

## 2026-06-12 — scripts/scout.sh build + start

**Issue:** Dev/prod build steps scattered; no single script for compile + serve.

**Resolution:**
- `scripts/scout.sh build dev` → `.venv` + `maturin develop --release`
- `scripts/scout.sh build production` → `dist/*.whl` + pip install into `.venv-prod`
- `scripts/scout.sh start` / `start production` → `scout serve` from matching venv
- `build dev` cleans + builds + **starts serve** (foreground); use `start` to serve without rebuild
- `build dev` cleans: stop-serve, `dist/`, `scout_core/target/`, `__pycache__`, stale pip `scout`/`scout_core`
- `prod` alias for `production`; sets `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`

**Ref:** `journal/2026-06-12-scout-build-script.md`

**Issue:** Pi rejects skill `name: search_scout` — only `a-z`, `0-9`, hyphens allowed.

**Resolution:**
- Template frontmatter `name: search-scout`
- Pi install path `.pi/skills/search-scout/` (not `search_scout`)
- Cursor/OpenCode keep `search_scout` dir for backward compat

**Fix existing install:** move `~/project/.pi/skills/search_scout` → `search-scout`, update name in SKILL.md

## 2026-06-12 — Code review docs + test reorg (Batch A+B)

**Issue:** Review flagged flat tests/, uncommented Cargo.toml, thin skill docs, no API test conventions, missing component READMEs, no OpenSpec cross-refs, no PR template.

**Resolution:**
- Tests → `tests/{api,cli,embed,integration}/` + shared `conftest.py`, `api/conftest.py` with `save_spaces_config()`
- READMEs: `scout_core/`, `scout/api/`, `scout/skill/`, `tests/`, `skills/search_scout/`
- Cargo.toml comment blocks (workspace + per-dep)
- `SKILL.md` expanded: install paths, injection, troubleshooting, Pi hyphen rule
- OpenSpec `See also:` cross-refs on all spec files
- `.github/pull_request_template.md`
- 39 pytest pass

**Ref:** `journal/2026-06-12-code-review-improvements.md`

## 2026-06-12 — OpenSpec validation (Batch C decision B)

**Issue:** No automated check for OpenSpec artifact structure or cross-ref link integrity; cross-change `See also:` links used wrong `../../` depth.

**Resolution:**
- `scripts/validate_openspec.py` — required change files, ADDED/MODIFIED + Scenario blocks, relative link resolve
- CI step + PR template checkbox
- Fixed cross-change links (`../../../` to sibling changes)
- `tests/openspec/test_validate_openspec.py`

**Run:** `python scripts/validate_openspec.py` | `scripts/scout.sh validate` | `make validate-openspec`

**Ref:** `journal/2026-06-12-openspec-validation.md`

## 2026-06-12 — OpenSpec validate discoverability (Batch C decision B+D)

**Issue:** Validator CI-only; devs may not know to run before OpenSpec edits.

**Resolution:**
- `scripts/scout.sh validate` subcommand
- `Makefile` target `validate-openspec`
- README dev section documents all three entry points

**Ref:** `journal/2026-06-12-openspec-validation.md`

## 2026-06-12 — api-contracts ↔ rest-api spec sync (Batch C decision C)

**Issue:** `GET /v1/spaces/list` in api-contracts + app.py but missing from rest-api OpenSpec.

**Resolution:**
- `validate_api_contracts_sync()` in `scripts/validate_openspec.py`
- Parses endpoints table + spec scenarios/requirements; symmetric diff
- Added List spaces requirement to `rest-api/spec.md`

**Ref:** `journal/2026-06-12-openspec-validation.md`

## 2026-06-12 — app.py ↔ api-contracts sync (Batch C decision 4)

**Issue:** Spec ↔ contracts sync didn't catch FastAPI route decorator drift.

**Resolution:**
- `validate_app_routes_sync()` — `@app.get/post(...)` vs api-contracts table
- Full chain: rest-api spec ↔ api-contracts.md ↔ scout/api/app.py

**Ref:** `journal/2026-06-12-openspec-validation.md`

## 2026-06-12 — chunk.rs UTF-8 slice panic on oversized symbols

**Issue:** Indexing panicked at `chunk.rs:87` — `split_oversized` sliced at byte offset 3072 inside multi-byte Greek char (`ὴ`). Token heuristic uses byte counts (`768 * 4`) but Rust str slices require char boundaries.

**Resolution:**
- Added `floor_char_boundary()`; align `start`/`end` before every slice
- If floored `end <= start`, advance to next full char (single-char minimum chunk)
- `extract_text` also floors bounds defensively
- Tests: `split_oversized_respects_utf8_boundaries`, `extract_text_floors_to_char_boundary`

**Ref:** `scout_core/src/chunk.rs`

## 2026-06-13 — `--embed-batch` CLI flag

**Issue:** Scout hardcoded 16 chunks per embed HTTP request; LM Studio eval batch (2048–4096) is separate server setting.

**Resolution:** `scout <space> reindex|setup --embed-batch N` (default 4096). Passes to `embed_texts_batched` → `run_reindex`.

**Usage:** `scout scout reindex` (auto) or `--embed-batch N` / `--reprobe-embed-batch`

**Ref:** `journal/2026-06-13-embed-batch-cli-flag.md`

## 2026-06-13 — Auto embed batch probe (hardware + provider)

**Issue:** Fixed batch 4096 still under-utilizes LM Studio; optimal size varies by GPU VRAM, model, chunk size.

**Resolution:** Default auto-resolve at reindex via **GET /models** metadata (`eval_batch_size`, `context_length`) — no embed trial requests. Formula: `eval_batch_size // chunk_tokens`. Fallback: host RAM estimate. Cache in config; `--reprobe-embed-batch` refreshes.

**Ref:** `journal/2026-06-13-auto-embed-batch-probe.md`, `scout/embed/batch_probe.py`, `journal/2026-06-12-chunk-utf8-boundary-fix.md`

## 2026-06-12 — Embed 401: wrong API key sent to local provider

**Issue:** Search/reindex 401 on LM Studio despite correct embed model + `lmstudio_api_key` in secrets. User also had `openrouter_api_key` set.

**Root cause:** `app.py` / `cli/main.py` used `secrets.get("openrouter_api_key") or get_embed_api_key(...)` — OpenRouter key always won when present, sent to LM Studio → 401.

**Resolution:** Use `get_embed_api_key(secrets, embed.provider)` only (provider-scoped lookup).

**Ref:** `journal/2026-06-12-embed-api-key-provider-fix.md`

## 2026-06-13 — Search 500: embed ConnectError (endpoint down)

**Issue:** `POST /v1/spaces/*/search` → 500, `httpx.ConnectError: All connection attempts failed` at `registry.py` embed POST. User also had stale `scout.pid`.

**Root cause:** Embed endpoint in config (`http://127.0.0.1:4321/v1`) had **no process listening** — connection refused. Not a scout_core or recent API-key code regression (that path gives 401, not ConnectError).

**Resolution:**
- Start local embed server on configured port (LM Studio → Developer → server port)
- Verify: `curl http://127.0.0.1:4321/v1/models`
- `scout stop-serve` clears stale PID; restart `scout serve`
- If 401 after connect works: update `lmstudio_api_key` in `~/.scout/secrets.yaml` via setup wizard

**Ref:** `journal/2026-06-13-embed-connect-error.md`

## 2026-06-13 — pipx `scout` name collision (4.0.0 vs 0.1.0)

**Issue:** `scout scout reindex/setup` → `server.py only accepts one argument` from pipx path.

**Root cause:** `pipx install scout` pulled **PyPI scout 4.0.0** (legacy Flask FTS doc search), not Scout 0.1.0 (code-graph search). CLI shapes incompatible.

**Resolution:**
```bash
pipx uninstall scout
pipx install dist/scout-0.1.0-*.whl   # or maturin build first
```
Dev fallback: `source .venv/bin/activate` or `scripts/scout.sh`.

**Future risk:** PyPI name `scout` taken by 4.0.0 — publish may need distinct package name.

**Ref:** `journal/2026-06-13-pipx-scout-name-collision.md`

## 2026-06-13 — chunk.rs UTF-8 panic via stale wheel

**Issue:** `scout reindex` panicked `chunk.rs:87` mid-char Greek slice — same bug fixed 2026-06-12 in source.

**Root cause:** pipx wheel built **before** `floor_char_boundary` fix. Source OK, binary stale.

**Resolution:** Rebuild + reinstall:
```bash
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin build --release --out dist
pipx uninstall scout && pipx install dist/scout-0.1.0-*.whl
```

**Ref:** `journal/2026-06-13-stale-wheel-utf8-panic.md`, `scout_core/src/chunk.rs`

## 2026-06-13 — code-reviewer-scout skill (index-first review)

**Issue:** AI code reviewers load full files into session → high token burn. No review-specific agent skill.

**Resolution:**
- New skill `skills/code-reviewer-scout/` — index-first escalation ladder (scope → search → node → full read last)
- Standalone install: `python -m scout.code_reviewer --agent cursor --project --scout-api URL --default-space SPACE`
- Helper: `skills/code-reviewer-scout/scripts/review_api.py` (path-scoped search, node lookup)
- Hyphen-only skill name/dir on all agents: `code-reviewer-scout`
- Does **not** modify setup wizard, `search_scout`, API, or CLI

**Install paths:**
| Agent | Project |
|-------|---------|
| Cursor | `<root>/.cursor/skills/code-reviewer-scout/` |
| Pi | `<root>/.pi/skills/code-reviewer-scout/` |
| OpenCode | `<root>/.opencode/skills/code-reviewer-scout/` |

**Ref:** `openspec/changes/ai-code-reviewer-scout/`, `journal/2026-06-13-ai-code-reviewer-scout.md`

## 2026-06-14 — Reviewer on-demand chunks (graph map + full read)

**Issue:** Code reviewer skill capped at ~500 char snippets; no graph-only module scope; no workspace file read API. Reviewers could not map connections then pull full source on demand.

**Resolution:**
- `GET /node/{id}` returns full `text` (sqlite chunk, not truncated)
- `GET /symbols?path_prefix=` — graph listing, no embed
- `GET /node/{id}/neighbors` — BFS expand, no embed
- `GET /file?rel_path=&start_line=&end_line=` — live workspace read (512 KiB cap)
- `code-reviewer-scout` skill: scope → map → read → audit
- `review_api.py`: `symbols`, `neighbors`, `file` commands

**Ref:** `openspec/changes/reviewer-on-demand-chunks/`, `journal/2026-06-14-reviewer-on-demand-chunks.md`

## 2026-06-14 — Stale scout serve → chunks path, not graph

**Issue:** Code reviewer still hit `/search` + `/node` (sqlite chunks) instead of graph-only `/symbols` + `/neighbors`. User saw chunk loads, not graph map.

**Cause:** `scout serve` on **8745** was old build — OpenAPI lacked `/symbols`, `/neighbors`, `/file`. Agent fell back to search/node. Project skill also had uninjected `{{SCOUT_API}}` placeholders.

**Resolution:**
1. `scout stop-serve` then `scout serve` — new serve picked **8746** (config `api_base_url` already 8746)
2. Verify graph routes: `curl -s http://127.0.0.1:8746/v1/openapi.json` lists `/symbols`, `/neighbors`, `/file`
3. Reinstall skill: `python -m scout.code_reviewer --agent cursor --project --scout-api http://127.0.0.1:8746/v1 --default-space scout --force`
4. Map phase: `GET /symbols?path_prefix=` + `GET /neighbors` — **no** sqlite/embed. Read phase: `GET /file` or `GET /node/{id}`

**Ref:** `journal/2026-06-14-stale-serve-graph-endpoints.md`

## 2026-06-14 — Stale scout.pid blocks serve (no orphan process)

**Issue:** `scout serve` → `already running (pid 1437)` but nothing listening on 8746.

**Cause:** Prior serve (pid 1437) died when parent terminal exited; `finally` pid cleanup never ran. `scout serve` only checks **pid file exists**, not process alive. No orphan scout process — just stale lock.

**Resolution:**
```bash
scout stop-serve   # removes stale pid if process dead
scout serve
```
Verify: `lsof -iTCP:8746 -sTCP:LISTEN` or `curl http://127.0.0.1:8746/v1/spaces/list`

**Note:** Unrelated uvicorn on 7860 is different app, not scout.

**Ref:** `journal/2026-06-14-stale-pid-blocks-serve.md`

## 2026-06-14 — Graph-only setup (no chunks)

**Issue:** Setup/reindex built sqlite chunks + embed pass though agents read full files from disk via `GET /file`. Slow setup, duplicate storage.

**Resolution:**
- Default setup/reindex: `graph.bin` + `manifest.json` only (`graph-only:v1`); no `index.db`, no embed wizard step
- Graph nodes carry `location_ref`: `{folder}={/rel_path}` (e.g. `scout_core=/scout_core/src/graph.rs`)
- Setup wizard: 2 branches (local / git clone)
- `POST /search` → 503 when no legacy `index.db`
- `GET /node/{id}` → metadata + `location_ref`; empty `text` without sqlite
- Skills updated: map → parse `location_ref` → `GET /file`

**Ref:** `openspec/changes/setup-graph-only-no-chunks/`, `journal/2026-06-14-setup-graph-only-no-chunks.md`


**Issue:** `scout scour search "auth"` → full Python traceback (`ValueError: unknown space: scour`).

**Resolution:**
- `scout/cli/errors.py` — map exceptions to friendly stderr; farewell `Thanks for using Scout.`
- `main()` top-level handler; `cli_fail()` for explicit errors
- Unknown space lists configured spaces + setup hint
- `SCOUT_DEBUG=1` shows traceback for unexpected errors
- Search validates space before embed (unknown space error first)

**Example:**
```
Unknown space: scour

Configured spaces: scout
Run: scout <space> setup

Thanks for using Scout.
```

**Ref:** `openspec/changes/cli-graceful-errors/`, `journal/2026-06-14-cli-graceful-errors.md`

## 2026-06-14 — Reviewer symbols-first (mandatory map before read)

**Issue:** Agents using `code-reviewer-scout` skipped `GET /symbols` and read files directly (IDE Read / `GET /file`), missing structural context and wasting tokens.

**Resolution:**
- SKILL.md hard rule: symbols mandatory before any read
- Reordered ladder: scope → symbols (required) → neighbors (optional) → read → audit
- Anti-patterns table (wrong vs right)
- `review_api.py map` alias for `symbols`
- Sync `.cursor/skills/code-reviewer-scout/` mirror

**Reinstall after update:**
```bash
python -m scout.code_reviewer --agent cursor --project --scout-api URL --default-space SPACE --force
```

**Ref:** `openspec/changes/reviewer-symbols-first/`, `journal/2026-06-14-reviewer-symbols-first.md`

## 2026-06-14 — search_scout default port 8747

**Issue:** `scout_api.py` failed without `SCOUT_API_URL`/config; built URLs with duplicate `/v1` (`/v1/v1/health`). Project serve on **8747**.

**Resolution:**
- Default fallback: `http://127.0.0.1:8747/v1` (after env + config.yaml)
- `normalize_base_url()` + `resolve_api_path()` — no duplicate `/v1`
- SKILL.md documents default 8747

**Resolution order:** `SCOUT_API_URL` → `config.yaml` `api_base_url` → 8747

**Ref:** `openspec/changes/search-scout-port-8747/`, `journal/2026-06-14-search-scout-port-8747.md`

## 2026-06-14 — session-embed-on-read (`scout serve --embed`)

**Issue:** Graph-only setup removed full-repo embed; agents lost semantic search without re-indexing entire repo.

**Policy exception:** One background daemon thread inside `scout serve --embed` only — not prescan/reindex. Dies with serve.

**Resolution:**
- `scout serve --embed` — in-memory graph cache + session index at `.scout/spaces/<space>/session_index.db`
- `GET /file` enqueues embed (dedupe by `rel_path`); worker embeds symbol chunks via existing provider
- `POST /search` → session index; `session_scoped: true`; graph-only serve still 503 without legacy `index.db`
- `GET /session/status`, `DELETE /session/index`
- Rust: `py_session_prepare_index`, `py_session_append_chunks`, `py_session_index_stats`
- Module: `scout/session/` (queue, store, worker, graph_cache, runtime)

**Ref:** `openspec/changes/session-embed-on-read/`, `journal/2026-06-14-session-embed-on-read.md`

## 2026-06-14 — setup src folder picker

**Issue:** Setup prompted full path for workspace root; monorepos need to index `src/` while running setup from repo root.

**Resolution:**
- Workspace prompt default `.` (= cwd); accepts `.` / `./`
- Numbered picker for immediate child dirs; `0` = entire workspace
- Junk dirs filtered (`node_modules`, `.git`, `.venv`, etc.)
- Git clone branch uses same picker after clone
- `SpaceEntry.root` = selected subfolder; skill install stays at workspace anchor

**Ref:** `openspec/changes/setup-src-folder-picker/`, `journal/2026-06-14-setup-src-folder-picker.md`

## 2026-06-14 — embed chunk compression

**Issue:** Session embed sent full symbol text to provider — slow/costly for verbose sources.

**Resolution:**
- `scout/embed/compress.py` — whitespace collapse before embed (`compress_chunks` default true)
- Optional `compress_strip_line_comments` in config
- sqlite stores compressed text; search/node return `compressed_text` field
- Full source still via `GET /file`

**Ref:** `openspec/changes/embed-chunk-compression/`, `journal/2026-06-14-embed-chunk-compression.md`

## 2026-06-14 — gitignore scan + RAM file cache

**Issue:** Large repos walked without `.gitignore`; session embed re-read disk per file; 45k-chunk scale impractical without filtering.

**Resolution:**
- `scan_workspace` honors `.gitignore` via `ignore` crate (`respect_gitignore` default true per space)
- `scout serve --embed` warms `FileCache` (parallel bulk read) after prescan RAM gate
- `--no-warm-cache` skips bulk warm; lazy populate on read
- Session embed worker + `GET /file` use cache when mtime fresh
- `GET /session/status` adds `cache_file_count`, `cache_bytes`, `cache_warm_seconds`
- Warm does **not** enqueue embed — read-triggered queue unchanged

**Ref:** `openspec/changes/gitignore-scan-ram-cache/`, `journal/2026-06-14-gitignore-scan-ram-cache.md`

## 2026-06-14 — file-level session embed default

**Issue:** Session embed still split files into per-symbol chunks; default embed batch 4096 too large for local providers.

**Resolution:**
- `build_file_chunks` defaults to one file-level embed unit per read (`symbol_chunks=True` opt-in)
- `DEFAULT_EMBED_BATCH` and config `embed_batch_size` default **10**
- Session worker passes resolved batch size to `embed_texts_batched`

**Ref:** `journal/2026-06-14-file-level-embed-default.md`

## 2026-06-14 — stale pipx scout ran full-repo embed at setup

**Issue:** `scout setup` prompted embed provider, built 45k chunks, batch 4096 — old pipx install at `~/.local/bin/scout`, not workspace `.venv`.

**Resolution:**
- Workspace code already graph-only; reinstall: `pipx install --force /path/to/scout` or use `.venv/bin/scout`
- `scout version` shows package path + `index mode: graph-only`
- Setup: optional embed config **after** graph index (default no) for `serve --embed` only
- Bump `0.1.1` to distinguish from stale pipx `0.1.0` full-embed build

## 2026-06-14 — setup API URL + optional embed crash

**Issue:** Setup did not detect running `scout serve` (bumped port when occupied). Optional embed step crashed (`SetupBranch` has no `uses_openrouter`).

**Resolution:**
- `probe_scout_health` + `discover_scout_api_url` scan 8741–8799; default prompt uses detected URL
- `ensure_api_port_available` keeps port when Scout health OK on it
- `configure_embed` prompts local/openrouter directly; no `SetupBranch.uses_openrouter`
- Embed setup errors surfaced instead of generic CLI failure

**Ref:** `journal/2026-06-14-setup-api-discovery-embed-fix.md`

## 2026-06-14 — CLI search graph path fallback

**Issue:** `scout <space> search README.md` failed on graph-only spaces — required legacy `index.db`.

**Resolution:**
- `scout/graph_find.py` — match `rel_path` / symbol in graph (no embed)
- `scout search` uses vector index when `index.db` exists; else graph path search
- Exact filename matches rank highest

**Ref:** `journal/2026-06-14-cli-graph-search.md`
