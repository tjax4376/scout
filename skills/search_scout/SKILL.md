---
name: search-scout
description: Search local codebase via Scout REST API with graph neighbor context.
---

# search-scout

Query Scout vector index for symbol-level code search with structural neighbors.

## Configuration

- `scout_api`: {{SCOUT_API}}
- `default_space`: {{DEFAULT_SPACE}}

## Usage

Ensure `scout serve` is running, then search:

```bash
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication middleware", "top_k": 5}'
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/spaces/{space}/search` | Vector search + neighbors |
| GET | `/spaces/{space}/node/{node_id}` | Full chunk lookup |
| POST | `/spaces/{space}/reindex` | Sync full rebuild |

## Response headers

- `X-Scout-Stale`: `true` if index outdated (still returns results)
- `X-Scout-Index-Version`: current index version

## Search request

```json
{
  "query": "required search text",
  "top_k": 10,
  "min_score": 0.0,
  "kinds": ["function"],
  "path_prefix": "src/"
}
```

## Notes

- Vector-only search (no FTS MVP1)
- Neighbors: anchor pivot, up 1 via `contains`, down 3 BFS
- CLI `scout <space> search` works without serve (pyo3 direct)
