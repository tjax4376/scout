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
