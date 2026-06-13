# Journal — Scout v2 MVP1 Grill Session

**Date:** 2026-06-12
**Author:** Cursor Agent (grill-me session)
**Version:** MVP1 scope v1

## Context

Grill-me session on `scope/scout-simple-mvp1.md` — Scout v2 generic code-graph + vector search for coding agents. Goal: resolve architecture ambiguities before OpenSpec proposal / implementation.

## Discussion Points

1. **Q1** — Separate standalone module from aiScout Cavern Scout; no MVP1 coupling.
2. **Q2/Q2b** — In-memory petgraph for reduced structure; text+vectors in vector store. User initially wanted Neo4j for vectors; pivoted to sqlite-vec (license, footprint, no Docker/server).
3. **Q3** — Separate embedding config; local-first with generic provider registry (not Ollama-specific); remote fallback.
4. **Q4** — Symbol-first chunking with file fallback and oversized symbol splits.
5. **Q5** — Named workspace spaces with isolated `.scout/` state per space.
6. **Q6** — MVP1 AST: TS/JS, Python, Rust, Go via tree-sitter; configs/docs file-only.
7. **Q7** — All local dev workstation; no Docker.
8. **Q8** — REST API on localhost with OpenAPI; skill integration; no webhook MVP1.
9. **Q9** — Rust `scout-core` engine; Python CLI/FastAPI/embed via pyo3.
10. **Q10** — Full rebuild indexing; staleness via manifest + `X-Scout-Stale` header.
11. **Q11** — Split config/secrets; gitignore; chmod 600; env override.
12. **Q12** — Prescan metrics with warn+confirm; hard stop at cap/100GB.
13. **Q13** — Deterministic blake3 `node_id` for graph↔chunk linkage.
14. **Q14** — Explicit MVP1 non-goals cut line (no chat LLM, webhook, incremental, Cavern bridge, etc.).
15. **Q15** — Distribution via PyPI + maturin wheels; `pipx install scout`.
16. **Q16** — `search_scout` skill shipped in repo; user picks agent (Cursor, Pi, OpenCode) at setup.
17. **Q17** — Separate API port scan (8741+) and embed endpoint scan; manual `scout serve`.
18. **Q18 (pass 2)** — Base petgraph = `contains` hierarchy. Full cross-entity analysis deferred to MVP2 (code review).
19. **Q19 (pass 2)** — Search includes `neighbors`: up 1 node, down 3 from hit. Add `imports`/`calls` to MVP1 graph if traversal requires them.
20. **Q20 (pass 2)** — Option A anchor pivot: up 1 `contains` parent, BFS down 3 (`contains`+`imports`+`calls`), cap 20 neighbor nodes.
21. **Q21 (pass 2)** — Search request: `query` required; optional `top_k`=10, `min_score`=0.0, `kinds[]`, `path_prefix`. No pagination.
22. **Q22 (pass 2)** — Search response: per-hit metadata + snippet + breadcrumb + nested neighbors (`edge`, `depth`). Top-level `stale`, `index_version`.
23. **Q23 (pass 2)** — Embed providers: OpenRouter (fetch models at setup, API key); local lmstudio/omlx/unsloth-studio; warn embedding/tool models only.
24. **Q24 (pass 2)** — Setup flow: interactive provider→endpoint→fetch/filter models→warn→pick→probe dims→prescan→index. Abort on failure.
25. **Q25 (pass 2)** — CLI setup/reindex/search = pyo3 direct (no serve). Serve = agent REST. Skill → HTTP only.
26. **Q26 (pass 2)** — Staleness: manifest mtime/size per file + embed config check; stale=true but still return results.
27. **Q27 (pass 2)** — Static imports/calls: workspace-only, unambiguous resolution; skip dynamic/unresolved; no type inference.
28. **Q28 (pass 2)** — Skill install: global + project-level (user picks at setup); cursor/pi/opencode paths; inject scout_api + default_space.
29. **Q29 (pass 2)** — pyo3 boundary: Rust owns scan/parse/graph/sqlite-vec/search/neighbors; Python owns embed HTTP + CLI/FastAPI; vectors passed Python→Rust.
30. **Q30 (pass 2)** — Local provider endpoint: user prompted for port range (suggested defaults); scan 127.0.0.1; probe /v1/models; manual URL fallback.
31. **Q31 (pass 2)** — Prescan estimates disk+RAM; hard fail if available < estimated ("not enough capacity"); `--force` bypasses 100GB cap only.
32. **Q32 (pass 2)** — Reindex sync only; no background jobs ever; atomic swap; long index time acceptable.
33. **Q33 (pass 2)** — One scout serve handles all configured spaces; single port/PID; unknown space → 404.
34. **Q34 (pass 2)** — Hardcoded skip dirs + optional space skip globs/paths; binary skipped; no .gitignore MVP1.
35. **Q35 (pass 2)** — Node kinds enum for graph + search filter: directory, file, module, class, struct, interface, enum, function, method, const.
36. **Q36 (pass 2)** — Grill closed. Scope ready for OpenSpec proposal.

## Code Changed

No implementation code. Documentation updated:

- `scope/scout-simple-mvp1.md` — full grill outcome with 17 resolved decisions, architecture pivot, non-goals, config layout
- `.memory/cards.md` — created with grill resolutions
- `journal/2026-06-12-grill-scout-mvp1.md` — this file

## Change Rationale

Grill pass 1 + pass 2 resolved all blocking dependencies before code generation. Major pivot from Neo4j to sqlite-vec. Pass 2 locked API contract, embed providers, pyo3 boundary, capacity gates, and permanent sync-only reindex policy.

## Test Plan (for future implementation)

- [ ] `pipx install scout` on macOS arm64 + linux x86_64
- [ ] `scout backend setup` indexes sample repo with TS + Python files
- [ ] Prescan warns on large dir; `--force` bypasses cap
- [ ] `scout serve` binds localhost scanned port; second instance fails on PID lock
- [ ] `POST /v1/spaces/backend/search` returns vector results + graph context
- [ ] `X-Scout-Stale: true` after file mtime change without reindex
- [ ] Skill install to Cursor/Pi/OpenCode paths via `--agent` flag
- [ ] Secrets not exposed via API; `secrets.yaml` mode 0600

## Security (PHA sketch)

- **Spoofing:** localhost-only API bind
- **Tampering:** manifest hash for index version
- **Repudiation:** N/A MVP1 (no audit log)
- **Information disclosure:** secrets split file; API never returns keys
- **DoS:** prescan hard cap + `--force`
- **Elevation:** chmod 600 on secrets; gitignore `.scout/`
