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
