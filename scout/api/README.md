# scout.api

FastAPI REST layer for agent-facing code search. Started by `scout serve`.

## Entry point

- `app.py` — `create_app()` registers all `/v1` routes

## Configuration

All `/v1` routes except optionally `GET /v1/health` require `Authorization: Bearer <token>` when `api.auth.enabled` is true. Admin routes (`POST /reindex`, `DELETE /session/index`) require the admin key. See root `api-contracts.md` **Authentication** section.

### Transport security

| Setting | Effect |
|---------|--------|
| `api.force_https: true` | HTTP requests redirect to HTTPS (`301`) |
| `SCOUT_FORCE_HTTPS=1` | Same as above via env |
| Non-loopback `api_base_url` | Auto-enables `force_https`; `http://` LAN URLs upgraded to `https://` on load |

Behind a TLS-terminating reverse proxy, set `X-Forwarded-Proto: https` so HSTS headers apply.

## Routes

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/health` | Liveness |
| GET | `/v1/spaces/list` | Reads `config.yaml` only (no scout_core) |
| POST | `/v1/spaces/{space}/search` | Embed query → scout_core search |
| GET | `/v1/spaces/{space}/node/{node_id}` | Full chunk lookup |
| POST | `/v1/spaces/{space}/reindex` | Sync rebuild, 409 if lock held |

Full request/response shapes: [`api-contracts.md`](../../api-contracts.md) at repo root.

## Hawkeye trace headers (optional)

When [Hawkeye](../hawkeye/README.md) runs reviews it sends:

| Header | Purpose |
|--------|---------|
| `X-Hawkeye-Session-Id` | Correlate Scout calls with a review session UUID |

Enable server-side request logging with `HAWKEYE_TRACE=1` (logs method, path, session id, status). Response bodies unchanged.

Route changes must update **api-contracts.md**, **rest-api/spec.md**, and **app.py** together (`scripts/scout.sh validate` enforces sync).

## Dependencies

- **Python:** fastapi, uvicorn, pydantic
- **Internal:** `scout.config`, `scout.indexing`, `scout.embed.registry`
- **Rust:** scout_core (via pyo3) for search/reindex paths

## Local dev

```bash
scout serve
curl -s http://127.0.0.1:8741/v1/health
```

Bind host/port from `.scout/config.yaml` → `api_base_url`.

## Tests

`tests/api/` — FastAPI `TestClient`, shared fixtures in `tests/api/conftest.py`.

## Specs

- `openspec/changes/scout-simple-mvp1/specs/rest-api/spec.md`
- `openspec/changes/scout-simple-mvp1/specs/vector-search/spec.md`
