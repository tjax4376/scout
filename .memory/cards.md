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

**Usage:** `scout scout reindex --embed-batch 128`

**Ref:** `journal/2026-06-13-embed-batch-cli-flag.md`, `journal/2026-06-12-chunk-utf8-boundary-fix.md`

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
