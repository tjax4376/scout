# Journal: Embed API key provider mismatch (401)

## Context

User reported Scout search failing with 401 despite using an embedding model (`text-embedding-nomic-embed-text-v1.5` via LM Studio). Error surfaced as "embedding provider not configured (401)".

## Discussion

- 401 is **auth failure**, not wrong model type. LM Studio requires `Authorization: Bearer <token>` on `/v1/embeddings`.
- Config at `~/.scout/config.yaml` had `provider: lmstudio`, model + endpoint correct, `lmstudio_api_key` present in secrets.
- Root cause: `app.py` and `cli/main.py` used `secrets.get("openrouter_api_key") or get_embed_api_key(...)` — when both keys exist, OpenRouter key sent to LM Studio → 401.

## Code changed

- `scout/api/app.py` — search + reindex: use `get_embed_api_key(secrets, embed.provider)` only
- `scout/cli/main.py` — reindex + search: same fix
- `tests/embed/test_auth.py` — test per-provider key selection

## Test plan

- `pytest tests/embed/test_auth.py -q`
- Manual: embed probe with lmstudio + openrouter keys both in secrets.yaml
