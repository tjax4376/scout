---
name: code-reviewer-scout
description: Token-efficient code review via Scout in-memory index — search snippets and graph neighbors before reading full files.
---

# code-reviewer-scout

Use Scout's in-memory code index (petgraph + sqlite-vec) for review context instead of loading whole source files into session. Query REST for snippets, symbols, and structural neighbors; expand only when indexed content is insufficient.

## Configuration

- `scout_api`: {{SCOUT_API}}
- `default_space`: {{DEFAULT_SPACE}}

## Golden rule

**Do not read full files first.** Load references from Scout index via `/search` and `/node/{id}`. Full file read is last resort only.

## Review escalation ladder

1. **Scope** — Set `path_prefix` to changed files/dirs from PR or diff context.
2. **Search** — `POST /search` with `top_k` 3–5. Use `snippet`, `breadcrumb`, and `neighbors` (imports, calls, contains).
3. **Expand** — `GET /node/{node_id}` when snippet is truncated or you need one symbol's full indexed chunk.
4. **Full read** — IDE Read tool only when steps 1–3 fail (full diff hunk, missing imports block, large refactor spanning many symbols).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Verify `scout serve` is up |
| GET | `/spaces/list` | List configured spaces |
| POST | `/spaces/{space}/search` | Vector search + graph neighbors |
| GET | `/spaces/{space}/node/{node_id}` | Full indexed chunk for one node |

Base URL is `scout_api` above (includes `/v1`).

## Path-scoped search (review step 1–2)

```bash
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "validate user token middleware",
    "top_k": 5,
    "path_prefix": "src/api/",
    "kinds": ["function", "method"]
  }'
```

Or use the helper:

```bash
python skills/code-reviewer-scout/scripts/review_api.py search {{DEFAULT_SPACE}} \
  "validate user token" --path-prefix src/api/ --top-k 5
```

## Node expand (review step 3)

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/node/NODE_ID_FROM_HIT"
```

```bash
python skills/code-reviewer-scout/scripts/review_api.py node {{DEFAULT_SPACE}} NODE_ID
```

## Stale index

Check response header `X-Scout-Stale: true` or JSON field `"stale": true`. Index may lag filesystem. For critical review, note staleness or ask user to reindex; do not assume missing symbols mean code is absent.

## Response fields to use

- `hits[].snippet` — ~500 char indexed excerpt (primary review context)
- `hits[].symbol`, `hits[].rel_path`, `hits[].start_line`/`end_line` — locate change
- `hits[].neighbors` — call sites, imports, parent file (in-memory graph, no file read)
- `hits[].score` — relevance ranking

## Token savings

| Approach | Typical cost |
|----------|--------------|
| Read 3 full files (500 lines each) | ~15k+ tokens |
| Scout search top_k=5 + 2 node fetches | ~2k tokens |

Prefer index references over session file loads.

## Notes

- Requires `scout serve` running and space indexed
- Vector search only (no FTS MVP1)
- Neighbors: anchor pivot, up 1 via `contains`, down 3 BFS, cap 20
