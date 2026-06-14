# API contracts documentation

**Context:** User requested `api-contracts.md` documenting all REST endpoints exposed by `scout serve`, including arguments and detailed syntax examples.

## Discussion points

1. Inventory routes from `scout/api/app.py` (FastAPI)
2. Request/response shapes from Pydantic models + Rust `SearchResponse` / `SearchHit` types
3. Path params, headers, error codes, node kinds, neighbor semantics
4. Base URL / port config from `scout/setup/api_url.py` and `config.yaml`
5. CLI parity vs HTTP-only endpoints

## Summary

- Four endpoints under `/v1`: health, search, node lookup, reindex
- OpenAPI at `/v1/openapi.json`; no auth MVP1
- Search body: `query` (required), `top_k`, `min_score`, `kinds`, `path_prefix`
- Response headers `X-Scout-Stale`, `X-Scout-Index-Version` on search/node
- Reindex returns 409 on concurrent lock; synchronous only

## Code changed

| File | Change |
|------|--------|
| `api-contracts.md` | New — full API contract reference with curl/httpie/Python/JS examples |
| `journal/2026-06-12-api-contracts.md` | New — session journal |
