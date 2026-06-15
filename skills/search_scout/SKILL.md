---
name: search-scout
description: Discover code via Scout graph index; read source from workspace using location_ref.
---

# search-scout

Map code structure via Scout graph, then read full source from disk. Default setup is **graph-only** (no full-repo vector index).

## Configuration

- `scout_api`: {{SCOUT_API}} (injected at setup from `config.yaml`)
- `default_space`: {{DEFAULT_SPACE}}
- **Default API** (when env/config unset): `http://127.0.0.1:8747/v1`

Resolution order for `scout_api.py`: `SCOUT_API_URL` → `~/.scout/config.yaml` → port **8747** default.

## Workflow

### Graph-first (default — no embed)

1. **Map** — `GET /symbols?path_prefix=…` or `GET /node/{id}/neighbors`
2. **Locate** — parse `location_ref` (`{folder}={/path/to/file}`)
3. **Read** — `GET /file?rel_path=…&start_line=&end_line=`

### Session search (`scout serve --embed`)

1. Configure embed provider in `config.yaml` + `secrets.yaml`
2. Run `scout serve --embed`
3. **Read** files via `GET /file` (enqueues background embed)
4. **Search** — `POST /search` — hits limited to read files; includes `compressed_text`

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/spaces/{space}/symbols` | List graph nodes under path (no embed) |
| GET | `/spaces/{space}/node/{id}/neighbors` | Expand graph connections |
| GET | `/spaces/{space}/node/{id}` | Node metadata + `compressed_text` when indexed |
| GET | `/spaces/{space}/file` | Read workspace source (full file or line range) |
| POST | `/spaces/{space}/search` | Vector search (503 graph-only; session index with `--embed`) |
| GET | `/spaces/{space}/session/status` | Session embed stats (`--embed` only) |
| POST | `/spaces/{space}/reindex` | Graph-only rebuild |

## Map symbols

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/symbols?path_prefix=src/"
```

## Read source

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/file?rel_path=src/auth.py&start_line=1&end_line=40"
```

## Session search

```bash
# After scout serve --embed and reading files via GET /file
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "auth handler", "top_k": 5}'
```

Response hits include `snippet` (short preview) and `compressed_text` (full indexed chunk). `session_scoped: true` when using `--embed`.

## Response headers

- `X-Scout-Stale`: `true` if index outdated
- `X-Scout-Index-Version`: current index version (`graph-only:v1`)

## Notes

- Graph-only spaces: use `/symbols` + `/file`; `/search` returns 503 without `--embed`
- `compressed_text` is whitespace-compressed before embed (config: `embed.compress_chunks`)
- Legacy `index.db` from older full-repo embed still searchable without `--embed`
- Setup runs from **repo root**; workspace default `.`; pick `src/` subfolder when prompted
