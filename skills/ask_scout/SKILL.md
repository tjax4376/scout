---
name: ask-scout
description: Ask Scout for code structure via the graph index without burning prompt/LLM tokens on bulk file reads.
---

# ask-scout

Map code structure through Scout's graph ask endpoint. Scout answers with compact symbols, edges, and `location_ref`s — **no embed, no LLM, no source bodies**. Use this before dumping files into the prompt.

## Configuration

- `scout_api`: {{SCOUT_API}} (injected at setup from `config.yaml`)
- `default_space`: {{DEFAULT_SPACE}}
- **Auth:** when Scout auth enabled, set `SCOUT_API_KEY` or `Authorization: Bearer` on all requests
- **Default API** (when env/config unset): `http://127.0.0.1:8747/v1`

Resolution order for `scout_api`: `SCOUT_API_URL` → `~/.scout/config.yaml` → port **8747** default.

## Token budget rule

1. Call **ask** first for structure questions.
2. Prefer hits + edges + `location_ref` over pasting whole files into the prompt.
3. Only then `GET /file` for **targeted** line ranges when you must read source.
4. Escalate to `search-scout` / `POST /search` (`scout serve --embed`) when keyword/graph match fails.

## Workflow

### 1. Health

```bash
curl -s -H "Authorization: Bearer $SCOUT_API_KEY" "{{SCOUT_API}}/health"
```

- **HTTP 200** → proceed
- Connection error / non-200 → skip ask; fall back carefully (do not invent structure)

### 2. Ask structure

```bash
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/ask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SCOUT_API_KEY" \
  -d '{
    "query": "<structure question keywords>",
    "top_k": 10,
    "expand_depth": 1,
    "max_nodes": 50
  }'
```

#### Request fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `query` | yes | — | Symbol/path keywords (1–5000 chars) |
| `top_k` | no | 10 | Seed hit cap (1–50) |
| `expand_depth` | no | 1 | Neighbor expand (0–2) |
| `max_nodes` | no | 50 | Total node cap (1–200) |
| `path_prefix` | no | — | Limit to path subtree |

#### Response (compact)

```json
{
  "query": "authenticate",
  "hits": [
    {
      "node_id": "...",
      "kind": "function",
      "symbol": "authenticate",
      "rel_path": "src/auth.py",
      "location_ref": "src=/src/auth.py",
      "start_line": 1,
      "end_line": 20,
      "score": 0.5
    }
  ],
  "edges": [{"from_id": "...", "to_id": "...", "kind": "calls"}],
  "total": 1,
  "mode": "graph",
  "truncated": false
}
```

- **HTTP 200** → use hits/edges
- **HTTP 400 / 422** → invalid query
- **HTTP 404** → unknown space or missing graph (run `scout <space> reindex`)
- **HTTP 401** → set bearer key

### 3. Targeted file read (only if needed)

```bash
curl -s -H "Authorization: Bearer $SCOUT_API_KEY" \
  "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/file?rel_path=src/auth.py&start_line=1&end_line=40"
```

## Anti-patterns

- Do **not** read entire packages into the prompt when ask hits suffice
- Do **not** expect natural-language prose answers from Scout ask (graph match only)
- Do **not** call embed/vector search unless structure ask returned nothing useful

## Notes

- Works on graph-only `scout serve` (no `--embed`)
- Shares search rate limit with `POST /search`
- Scout ask performs **no prompt/LLM processing**
