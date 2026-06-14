# Journal: Scout search 500 — embed ConnectError

## Context

User reported `POST /v1/spaces/scout/search` returning 500 with `httpx.ConnectError: All connection attempts failed`. Also suspected orphaned `scout serve` process.

## Discussion

- Stack trace: failure at `scout/embed/registry.py` `OpenAICompatProvider.embed()` POST to configured embed endpoint — not scout_core or vector search.
- `~/.scout/config.yaml`: `provider: lmstudio`, `endpoint: http://127.0.0.1:4321/v1`.
- Port check: **nothing listening on 4321** at time of investigation → connection refused → ConnectError.
- Port 1234 has a Python process (LM Studio default) but user config targets 4321.
- Stale `~/.scout/scout.pid` held dead PID 62455; `scout stop-serve` removed it. No live orphan `scout serve` found.
- Recent code change (embed API key fix) switches to provider-scoped key only — would cause **401**, not ConnectError. Not root cause here.
- Stored `lmstudio_api_key` returns 401 against port 1234 when tested — separate auth issue if endpoint is corrected.

## Code changed

None — operational/config issue.

## Test plan

1. Start embed server on port 4321 (LM Studio server settings → port 4321) OR re-run `scout <space> setup` to rescan endpoint.
2. `curl http://127.0.0.1:4321/v1/models` → expect 200 (with valid API key if required).
3. `scout stop-serve` then `scout serve`.
4. `curl -X POST http://127.0.0.1:8745/v1/spaces/scout/search -H 'Content-Type: application/json' -d '{"query":"test","top_k":3}'` → expect 200.
