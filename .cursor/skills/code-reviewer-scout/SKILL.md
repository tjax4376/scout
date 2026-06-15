---
name: code-reviewer-scout
description: Graph-first code review via Scout — map connections, read full source on demand.
---

# code-reviewer-scout

Use Scout's graph index to **map** structure and connections first, then **read** targeted file ranges on demand. Never open a file blind — list symbols for the path first, then read using `node_id` and line numbers from that list.

## Configuration

- `scout_api`: {{SCOUT_API}}
- `default_space`: {{DEFAULT_SPACE}}

## Hard rule — symbols before read

**Before** any `GET /file`, `GET /node/{id}`, or IDE Read on a path, you **MUST** run `GET /symbols?path_prefix=…` for that module or directory and record `node_id`, `symbol`, `start_line`, `end_line`, and `location_ref`.

Do not skip this step. Do not guess line ranges. Do not read whole files when symbols can narrow the scope.

## Review escalation ladder

1. **Scope** — Set `path_prefix` or target `rel_path` from PR/diff/changed modules.
2. **Symbols (required)** — Graph-only, no embed:
   - `GET /symbols?path_prefix=…` — list every symbol in scope; note `node_id`, lines, `location_ref`
   - Pick symbols to audit before any read
3. **Connections (optional)** — Expand from symbols of interest:
   - `GET /node/{id}/neighbors` — follow imports/calls/contains
   - `POST /search` — semantic discovery when `scout serve --embed` is running (session index from files you read); 503 on graph-only serve
4. **Read (targeted)** — Only after step 2:
   - Parse `location_ref` (`folder=/path/to/file`) → `rel_path`
   - `GET /file?rel_path=…&start_line=&end_line=` using lines **from symbol results** (authoritative full source)
   - `GET /node/{id}` for metadata + indexed `compressed_text` when embedded
5. **Audit** — Apply review rules on loaded text; repeat symbols/neighbors/read for traced connections.

## Anti-patterns

| Wrong | Right |
|-------|-------|
| IDE Read `scout/api/app.py` immediately | `map` / `symbols` on `scout/api/` → pick node → `file` with symbol lines |
| `GET /file` without prior symbols for that prefix | Always symbols first for the directory or file's parent prefix |
| Read entire file when one function changed | Symbols list → read only that symbol's `start_line`–`end_line` |
| Use `snippet` alone for audit | `GET /file` for source; `compressed_text` or `text` for indexed chunk |
| Search before reading files (`--embed`) | Read target files via `GET /file` first — only read files are searchable |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Verify `scout serve` is up |
| GET | `/spaces/list` | List configured spaces |
| GET | `/spaces/{space}/symbols` | List graph nodes under `path_prefix` — **run first** |
| GET | `/spaces/{space}/node/{id}/neighbors` | Expand graph connections |
| POST | `/spaces/{space}/search` | Session vector search (`scout serve --embed` only) |
| GET | `/spaces/{space}/session/status` | Embed queue depth, file count (`--embed` only) |
| GET | `/spaces/{space}/node/{id}` | Node metadata + `compressed_text` when indexed |
| GET | `/spaces/{space}/file` | Read workspace file or line range (live disk) |

Base URL is `scout_api` above (includes `/v1`).

## Map symbols (step 2 — required)

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/symbols?path_prefix=scout/embed/"
```

```bash
python skills/code-reviewer-scout/scripts/review_api.py map {{DEFAULT_SPACE}} scout/embed/
# alias: symbols
python skills/code-reviewer-scout/scripts/review_api.py symbols {{DEFAULT_SPACE}} scout/embed/
```

Expand connections from a symbol you picked:

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/node/NODE_ID/neighbors?depth=3&max_nodes=50"
python skills/code-reviewer-scout/scripts/review_api.py neighbors {{DEFAULT_SPACE}} NODE_ID
```

## Read on demand (step 4 — after symbols)

Parse `location_ref` from the symbol you chose (e.g. `scout=/scout/api/app.py` → `rel_path=scout/api/app.py`):

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/file?rel_path=scout/api/app.py&start_line=80&end_line=150"
```

Node metadata + indexed chunk (when session-embedded):

```bash
curl -s "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/node/NODE_ID"
python skills/code-reviewer-scout/scripts/review_api.py node {{DEFAULT_SPACE}} NODE_ID
python skills/code-reviewer-scout/scripts/review_api.py file {{DEFAULT_SPACE}} scout/api/app.py --start-line 80 --end-line 150
```

## Semantic discovery (optional, `--embed` only)

Requires `scout serve --embed` with embed provider configured. **Read files via `GET /file` first** — each read enqueues background embed (deduped).

```bash
python skills/code-reviewer-scout/scripts/review_api.py search {{DEFAULT_SPACE}} \
  "auth token validation" --path-prefix scout/api/ --top-k 5
```

Search hits include `compressed_text` (full indexed chunk body, whitespace-compressed before embed) and short `snippet`. Use `GET /file` for authoritative source.

## Stale index

Check `X-Scout-Stale: true` or JSON `"stale": true`. File read uses live disk; index pointers may lag — reindex before critical security audit.

## Response fields

| Endpoint | Key fields |
|----------|------------|
| `/symbols` | `symbols[].node_id`, `location_ref`, `rel_path`, `start_line`, `end_line`, `symbol` |
| `/neighbors` | `neighbors[].edge`, `depth`, `location_ref`, `rel_path` |
| `/search` | `hits[].snippet`, `hits[].compressed_text`, `session_scoped: true` |
| `/session/status` | `queue_depth`, `embedded_file_count`, `worker_running`, `chunk_count` |
| `/node/{id}` | `location_ref`, `compressed_text`, `text` (empty when not indexed) |
| `/file` | `text`, `start_line`, `end_line`, `total_lines` |

## Notes

- Requires `scout serve` and indexed space
- Graph endpoints work without embed provider
- Session search: `scout serve --embed` + embed config in `config.yaml`
- Neighbors on search hits: depth ≤3, cap 20; `/neighbors` endpoint: depth ≤5, cap 100
