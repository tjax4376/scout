---
name: ask-memory
description: Query Scout's memory store for relevant context about the user's current prompt.
---

# ask-memory

Query Scout's memory store for relevant context about the user's current prompt. Use this skill at the start of each prompt submission to gather background information before processing the request.

## Configuration

- `scout_api`: https://192.168.40.163:8741/v1 (injected at setup from `config.yaml`)
- **Auth:** when Scout auth enabled, set `SCOUT_API_KEY` or `Authorization: Bearer` on all requests
- **TLS:** self-signed cert — use `curl -k` (or `verify=False`) on all HTTPS requests
- **Default API** (when env/config unset): `http://127.0.0.1:8747/v1`

Resolution order for `scout_api`: `SCOUT_API_URL` → `~/.scout/config.yaml` → port **8747** default.

## Workflow

### 1. Detect Scout availability

Send `GET /v1/health` to the Scout API.

- **HTTP 200** → Scout is running. Proceed to API mode (section 2).
- **Connection error or non-200** → Scout is not running. Skip memory context and proceed with the prompt.

### 2. API mode: query relevant memories

When Scout is running, call the ask-memory endpoint with the user's prompt:

```bash
curl -sk -X POST "https://192.168.40.163:8741/v1/memory/ask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SCOUT_API_KEY" \
  -d '{
    "query": "<user prompt text>"
  }'
```

Space-scoped alias `POST /v1/spaces/{space}/memory/ask` also works (same global store).

#### Request fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | The user's prompt text (1-5000 chars) |

#### Responses

- **HTTP 200** → Memory search results. Response includes `memories` array, `total` count, and echoed `query`.
- **HTTP 400** → Invalid query (empty or too long).
- **HTTP 404** → Unknown space.
- **HTTP 500** → Server error.

#### Response format

```json
{
  "memories": [
    {
      "id": "uuid",
      "title": "Memory title",
      "body": "Memory content",
      "category": "category",
      "tags": ["tag1", "tag2"],
      "created_at": "2026-07-13T...",
      "rel_path": "scout/memories/uuid.md"
    }
  ],
  "total": 3,
  "query": "user's prompt text"
}
```

### 3. Incorporate memories into context

After receiving the response, read the relevant memories and incorporate them into your understanding of the user's request. Focus on:

- **Category matches**: Memories in categories relevant to the prompt topic
- **Title matches**: Memory titles that directly relate to the prompt
- **Body content**: Specific details, preferences, or context stored in memory bodies

Use the returned memories to:
- Understand the user's preferences and past decisions
- Recall project context and architecture decisions
- Reference previous interactions or configurations
- Avoid repeating information the user has already provided

### 4. Handle errors gracefully

If the API call fails (connection error, timeout, server error), proceed with the prompt without memory context. Log the error but do not fail the request.

```
# If API fails:
# 1. Log: "Warning: could not fetch memory context — proceeding without"
# 2. Continue with the prompt normally
```

## Usage examples

### Gather context before answering a coding question

```
# User asks: "How should I implement auth in this project?"
# 1. Call POST /memory/ask with the prompt as query
# 2. Response returns memories about auth patterns, past decisions
# 3. Incorporate those memories into the answer
```

### Check for project-specific conventions

```
# User asks: "Write a new API endpoint for user profiles"
# 1. Call POST /memory/ask with the prompt as query
# 2. Response returns memories about API conventions, naming patterns
# 3. Follow those conventions in the implementation
```

### Handle Scout being unavailable

```
# 1. Health check fails (connection refused)
# 2. Skip memory context, proceed with prompt
# 3. No error to report — memory context is helpful but not required
```

### Incorporate returned memories

```
# Response: 2 memories about code style preferences
# → "Based on your stored preferences, I'll use: [summarize relevant memories]"
# → Reference specific memories when making decisions
```

## Error handling

### Connection failure
If Scout is unreachable, proceed with the prompt. Do not retry or block.

### Empty results
If no memories match the query, proceed normally. This is expected for new users or new topics.

### API error
If the endpoint returns an error, log it and proceed with the prompt. Do not fail the request.
