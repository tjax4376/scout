# Scout API Contracts

REST API exposed by `scout serve`. All routes live under `/v1`. Base URL configured at setup as `api_base_url` in `.scout/config.yaml` (default `http://127.0.0.1:8741/v1`).

**Metadata:** v0.1.0 | Scout Contributors | 2026-06-12

---

## Overview

| Item | Value |
|------|-------|
| Start server | `scout serve` |
| Stop server | `scout stop-serve` |
| Default port | `8741` (scan range `8741`–`8799` at setup if busy) |
| Base URL format | `http://<host>:<port>/v1` |
| Auth (MVP1) | None |
| Content-Type (POST bodies) | `application/json` |
| OpenAPI spec | `GET /v1/openapi.json` |
| Interactive docs | `GET /docs` (FastAPI Swagger UI) |
| Multi-space | One `scout serve` serves all spaces in `config.yaml` |

Path convention: `{BASE}` = configured base URL including `/v1`, e.g. `http://127.0.0.1:8741/v1`.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Liveness check |
| `GET` | `/v1/spaces/list` | List configured spaces |
| `POST` | `/v1/spaces/{space}/search` | Vector search + graph neighbors |
| `GET` | `/v1/spaces/{space}/node/{node_id}` | Lookup single indexed node |
| `POST` | `/v1/spaces/{space}/reindex` | Synchronous full index rebuild |

---

## 1. Health

### `GET /v1/health`

No parameters. No request body.

#### Response `200 OK`

```json
{
  "status": "ok"
}
```

#### Examples

```bash
curl -s "{BASE}/health"
```

```bash
http GET "{BASE}/health"
```

```python
import httpx

resp = httpx.get("http://127.0.0.1:8741/v1/health")
resp.raise_for_status()
print(resp.json())  # {"status": "ok"}
```

---

## 2. List spaces

### `GET /v1/spaces/list`

Returns all spaces from `.scout/config.yaml` served by this `scout serve` instance. No parameters. No request body. Does not require `scout_core`.

#### Response `200 OK`

```json
{
  "spaces": [
    {
      "name": "alpha",
      "root": "/home/dev/alpha",
      "skip_globs": [],
      "skip_paths": ["vendor/"]
    },
    {
      "name": "myapp",
      "root": "/home/dev/myapp",
      "skip_globs": ["*.log"],
      "skip_paths": []
    }
  ]
}
```

Spaces sorted by `name` ascending. Empty config → `"spaces": []`.

#### Examples

```bash
curl -s "{BASE}/spaces/list"
```

```bash
http GET "{BASE}/spaces/list"
```

Python:

```python
import httpx

resp = httpx.get("http://127.0.0.1:8741/v1/spaces/list")
resp.raise_for_status()
for space in resp.json()["spaces"]:
    print(space["name"], space["root"])
```

Pick first space for search:

```bash
SPACE=$(curl -s "{BASE}/spaces/list" | jq -r '.spaces[0].name')
curl -s -X POST "{BASE}/spaces/${SPACE}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "main entry point"}'
```

---

## 3. Search

### `POST /v1/spaces/{space}/search`

Vector similarity search over indexed code chunks. Query text is embedded server-side using the space's configured embed provider. Results include snippets, breadcrumbs, and structural neighbors.

#### Path parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `space` | string | yes | Space name from `.scout/config.yaml` → `spaces.<name>` |

#### Request body (JSON)

| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `query` | string | **yes** | — | non-empty recommended | Natural-language or code search text |
| `top_k` | integer | no | `10` | `1`–`100` | Max hits to return |
| `min_score` | number | no | `0.0` | `0.0`–`1.0` | Minimum cosine similarity score |
| `kinds` | string[] | no | `null` | see [Node kinds](#node-kinds) | Exact kind filter; omit for all kinds |
| `path_prefix` | string | no | `null` | prefix match on `rel_path` | Limit hits to paths starting with this prefix |

Unknown values in `kinds` are ignored. If every kind is invalid, no kind filter is applied.

#### Response `200 OK`

Body:

```json
{
  "hits": [
    {
      "node_id": "a1b2c3d4e5f67890",
      "kind": "function",
      "symbol": "handleAuth",
      "rel_path": "src/api/handlers.ts",
      "start_line": 42,
      "end_line": 78,
      "score": 0.87,
      "snippet": "export async function handleAuth(req: Request) {\n  const token = req.headers.get('authorization')…",
      "breadcrumb": "src > api > handlers.ts > handleAuth",
      "neighbors": [
        {
          "node_id": "f9e8d7c6b5a43210",
          "kind": "file",
          "symbol": null,
          "rel_path": "src/api/handlers.ts",
          "edge": "contains",
          "depth": 1
        },
        {
          "node_id": "1122334455667788",
          "kind": "function",
          "symbol": "verifyToken",
          "rel_path": "src/auth/token.ts",
          "edge": "imports",
          "depth": 2
        }
      ]
    }
  ],
  "stale": false,
  "index_version": "8f3a2b1c9d0e"
}
```

Response headers:

| Header | Values | Meaning |
|--------|--------|---------|
| `X-Scout-Stale` | `true` / `false` | Index may be outdated vs filesystem or embed config |
| `X-Scout-Index-Version` | 12-char hex string | Current index version identifier |

**Score:** `1.0 - cosine_distance` (higher = more similar).

**Snippet:** Up to ~500 characters of chunk text; longer text truncated with `…`.

**Neighbors:** Anchor pivot — up 1 via `contains` to parent, then BFS down depth ≤ 3 via `contains`, `imports`, `calls`. Max 20 neighbors; anchor excluded.

#### Error responses

| Status | Condition | Body example |
|--------|-----------|--------------|
| `404` | Unknown `space` | `{"detail": "unknown space: myapp"}` |
| `422` | Invalid body (e.g. `top_k` out of range) | FastAPI validation `detail` array |
| `500` | `scout_core` not installed | `{"detail": "scout_core not installed"}` |

#### Examples

Minimal search:

```bash
curl -s -X POST "{BASE}/spaces/myapp/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication middleware"}'
```

With all optional fields:

```bash
curl -s -X POST "{BASE}/spaces/myapp/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "parse config file",
    "top_k": 5,
    "min_score": 0.35,
    "kinds": ["function", "method"],
    "path_prefix": "src/api/"
  }'
```

Inspect staleness headers:

```bash
curl -s -D - -o /tmp/scout-search.json \
  -X POST "{BASE}/spaces/myapp/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "error handling", "top_k": 3}'

grep -i x-scout /dev/stdin  # from -D - headers
jq '.hits[].symbol, .stale' /tmp/scout-search.json
```

Python:

```python
import httpx

BASE = "http://127.0.0.1:8741/v1"
SPACE = "myapp"

resp = httpx.post(
    f"{BASE}/spaces/{SPACE}/search",
    json={
        "query": "database connection pool",
        "top_k": 10,
        "min_score": 0.0,
        "kinds": ["function"],
        "path_prefix": "src/",
    },
    timeout=120.0,
)
resp.raise_for_status()

stale = resp.headers.get("X-Scout-Stale")
version = resp.headers.get("X-Scout-Index-Version")
data = resp.json()

for hit in data["hits"]:
    print(f"{hit['score']:.2f}  {hit['breadcrumb']}")
    print(f"  id={hit['node_id']}  neighbors={len(hit['neighbors'])}")
```

JavaScript (fetch):

```javascript
const BASE = "http://127.0.0.1:8741/v1";
const SPACE = "myapp";

const resp = await fetch(`${BASE}/spaces/${SPACE}/search`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "retry logic for failed requests",
    top_k: 5,
  }),
});

if (!resp.ok) throw new Error(await resp.text());
console.log("stale:", resp.headers.get("X-Scout-Stale"));
const data = await resp.json();
console.log(data.hits.map((h) => [h.score, h.breadcrumb]));
```

---

## 4. Node lookup

### `GET /v1/spaces/{space}/node/{node_id}`

Fetch one indexed node by ID (from search results). Same hit shape as search, but no similarity ranking context.

#### Path parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `space` | string | yes | Space name |
| `node_id` | string | yes | 16-char hex node ID from search `hits[].node_id` |

#### Response `200 OK`

Single `SearchHit` object (not wrapped in `hits`):

```json
{
  "node_id": "a1b2c3d4e5f67890",
  "kind": "function",
  "symbol": "handleAuth",
  "rel_path": "src/api/handlers.ts",
  "start_line": 42,
  "end_line": 78,
  "score": 0.0,
  "snippet": "export async function handleAuth(req: Request) { … }",
  "breadcrumb": "src > api > handlers.ts > handleAuth",
  "neighbors": []
}
```

`score` is always `0.0` for direct lookup (no vector query). `snippet` is still capped at ~500 characters.

Response headers: same `X-Scout-Stale` and `X-Scout-Index-Version` as search.

#### Error responses

| Status | Condition | Body example |
|--------|-----------|--------------|
| `404` | Unknown `space` | `{"detail": "unknown space: myapp"}` |
| `404` | Unknown `node_id` | `{"detail": "node a1b2c3d4e5f67890"}` |
| `500` | `scout_core` not installed | `{"detail": "scout_core not installed"}` |

#### Examples

```bash
NODE_ID="a1b2c3d4e5f67890"
curl -s "{BASE}/spaces/myapp/node/${NODE_ID}"
```

```bash
http GET "{BASE}/spaces/myapp/node/a1b2c3d4e5f67890"
```

Follow-up after search:

```bash
NODE_ID=$(curl -s -X POST "{BASE}/spaces/myapp/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "handleAuth", "top_k": 1}' \
  | jq -r '.hits[0].node_id')

curl -s "{BASE}/spaces/myapp/node/${NODE_ID}" | jq '.snippet, .neighbors'
```

Python:

```python
import httpx

node_id = "a1b2c3d4e5f67890"
resp = httpx.get(f"http://127.0.0.1:8741/v1/spaces/myapp/node/{node_id}")
resp.raise_for_status()
node = resp.json()
print(node["rel_path"], node["start_line"], node["end_line"])
```

---

## 5. Reindex

### `POST /v1/spaces/{space}/reindex`

Synchronous full rebuild: scan → parse → graph → embed → atomic index swap. Blocks until complete. No request body.

#### Path parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `space` | string | yes | Space name |

#### Response `200 OK`

```json
{
  "index_version": "8f3a2b1c9d0e",
  "status": "ok"
}
```

`index_version` is a 12-character hex string derived from embed config (`provider:model:dimensions`).

#### Error responses

| Status | Condition | Body example |
|--------|-----------|--------------|
| `404` | Unknown `space` | `{"detail": "unknown space: myapp"}` |
| `409` | Reindex already running (same or other space) | `{"detail": "reindex in progress"}` |
| `500` | Other failure (embed error, disk, etc.) | `{"detail": "<message>"}` |

Only one reindex at a time globally (in-process lock).

#### Examples

```bash
curl -s -X POST "{BASE}/spaces/myapp/reindex"
```

```bash
http POST "{BASE}/spaces/myapp/reindex"
```

Python (long-running):

```python
import httpx

resp = httpx.post(
    "http://127.0.0.1:8741/v1/spaces/myapp/reindex",
    timeout=None,  # wait for full rebuild
)
if resp.status_code == 409:
    print("reindex already running")
else:
    resp.raise_for_status()
    print(resp.json())  # {"index_version": "...", "status": "ok"}
```

---

## Reference

### Node kinds

Valid `kinds` filter values (lowercase):

| Kind | Typical use |
|------|-------------|
| `directory` | Folder nodes |
| `file` | Whole-file fallback chunks |
| `module` | Module-level symbols |
| `class` | Class definitions |
| `struct` | Struct definitions |
| `interface` | Interface definitions |
| `enum` | Enum definitions |
| `function` | Top-level functions |
| `method` | Methods on types |
| `const` | Constants |

### Neighbor edge types

| Edge | Meaning |
|------|---------|
| `contains` | Structural containment (dir → file → symbol) |
| `imports` | Static import relationship (best-effort) |
| `calls` | Static call relationship (best-effort) |

### Staleness

Index marked stale when:

- Files added, removed, or changed on disk vs manifest
- Embed provider, model, or dimensions changed

Stale indexes still return results. Check `stale: true` in JSON or `X-Scout-Stale: true` header, then `POST .../reindex`.

### Configuration

From `.scout/config.yaml`:

```yaml
api_base_url: http://127.0.0.1:8741/v1
api_port: 8741
spaces:
  myapp:
    root: /path/to/project
    skip:
      globs: []
      paths: []
embed:
  provider: lmstudio   # or openrouter, omlx, unsloth-studio
  model: text-embedding-...
  endpoint: http://127.0.0.1:1234/v1
  dimensions: 768
```

`scout serve` binds host/port parsed from `api_base_url`. LAN hosts supported if configured at setup.

### CLI vs API

| Action | CLI (no serve) | REST API |
|--------|----------------|----------|
| Search | `scout <space> search "<query>" [--top-k N]` | `POST /v1/spaces/{space}/search` |
| Reindex | `scout <space> reindex [--force]` | `POST /v1/spaces/{space}/reindex` |
| Health | — | `GET /v1/health` |
| List spaces | — | `GET /v1/spaces/list` |
| Node lookup | — | `GET /v1/spaces/{space}/node/{node_id}` |

CLI always uses pyo3 direct calls; it does not route through HTTP even when serve is running.

### Error envelope (FastAPI)

Most errors:

```json
{"detail": "human-readable message"}
```

Validation errors (`422`):

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "top_k"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0
    }
  ]
}
```

---

## Full workflow example

```bash
BASE="http://127.0.0.1:8741/v1"
SPACE="myapp"

# 1. Health
curl -s "$BASE/health"

# 2. List spaces
curl -s "$BASE/spaces/list" | jq '.spaces[].name'

# 3. Search
curl -s -X POST "$BASE/spaces/$SPACE/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "user session validation", "top_k": 3}' \
  | tee /tmp/search.json

# 4. Fetch top hit details
NODE=$(jq -r '.hits[0].node_id' /tmp/search.json)
curl -s "$BASE/spaces/$SPACE/node/$NODE" | jq .

# 5. Reindex if stale
if [ "$(jq -r '.stale' /tmp/search.json)" = "true" ]; then
  curl -s -X POST "$BASE/spaces/$SPACE/reindex"
fi
```
