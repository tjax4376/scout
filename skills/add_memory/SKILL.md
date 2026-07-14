---
name: add-memory
description: Contribute structured knowledge ("memories") to Scout via the add-memory API, with offline caching when Scout is not running.
---

# add-memory

Contribute structured knowledge to Scout's memory store. Agents use this skill when they learn something worth remembering — API design decisions, architecture notes, bug fixes, or any structured insight — during a session.

## Configuration

- `scout_api`: {{SCOUT_API}} (injected at setup from `config.yaml`)
- `default_space`: {{DEFAULT_SPACE}}
- **Auth:** when Scout auth enabled, set `SCOUT_API_KEY` or `Authorization: Bearer` on all requests
- **Default API** (when env/config unset): `http://127.0.0.1:8747/v1`

Resolution order for `scout_api`: `SCOUT_API_URL` → `~/.scout/config.yaml` → port **8747** default.

## Workflow

### 1. Detect Scout availability

Send `GET /v1/health` to the Scout API.

- **HTTP 200** → Scout is running. Proceed to API mode (section 2).
- **Connection error or non-200** → Scout is not running. Fall back to cache mode (section 3).

### 2. API mode: add memory directly

When Scout is running, call the memory creation endpoint:

```bash
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/memory" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SCOUT_API_KEY" \
  -d '{
    "title": "Memory title",
    "body": "Memory body content",
    "category": "optional-category",
    "tags": ["tag1", "tag2"]
  }'
```

#### Request fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Short descriptive title |
| `body` | string | yes | Memory content (markdown supported) |
| `category` | string | no | Category for organization; omit to get suggestions |
| `tags` | string[] | no | Optional tags for filtering |

#### Responses

- **HTTP 201** → Memory created. Response includes the memory object with `id`, `title`, `body`, `category`, `tags`, `created_at`, and `rel_path`.
- **HTTP 409** → No category provided. Response includes `suggested_categories` array. The agent should retry with one of the suggested categories.
- **HTTP 404** → Unknown space.
- **HTTP 400** → Validation error (e.g., body > 10KB).

#### Body size limit

Bodies exceeding **10KB** are rejected. The skill must check body length before sending and report an error to the agent if exceeded.

### 3. Cache mode: store locally when Scout is unavailable

When Scout is not running (health check fails), cache the memory as a markdown file in the workspace root's `.scout-memories-cache/` directory.

#### Cache directory

- Path: `.scout-memories-cache/` in the workspace root
- Auto-created on first write if it does not exist

#### Cache file format

One markdown file per memory, named `{id}.md`:

```yaml
---
id: <uuid>
title: <memory title>
body: <memory body>
category: <optional category>
tags: [<optional tags>]
created_at: <ISO 8601 timestamp>
space: <space name>
---

<memory body as markdown>
```

#### Frontmatter fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (UUID) | yes | Unique identifier |
| `title` | string | yes | Memory title |
| `body` | string | yes | Memory content |
| `category` | string | no | Category |
| `tags` | string[] | no | Tags |
| `created_at` | string (ISO 8601) | yes | Creation timestamp |
| `space` | string | yes | Space name |

#### Body size limit

Bodies exceeding 10KB are rejected in cache mode as well. Report the error to the agent.

### 4. Flush cached memories when Scout becomes available

On subsequent invocations when Scout is running, flush all cached memories before adding the new one.

#### Flush procedure

1. Read all `.md` files from `.scout-memories-cache/`
2. Sort by filename (natural/lexicographic order; UUID filenames provide deterministic ordering)
3. For each file, send `POST /v1/spaces/{space}/memory` with the frontmatter data
4. On **success**: remove the file from the cache directory
5. On **failure** (API error, 409, etc.): rename the file to `{id}.md.failed` and keep in cache for inspection

#### Flush ordering

Cached memories are flushed **first**, then the new memory is added. This ensures all pending memories are delivered before the current operation.

#### Concurrent flush safety

Use a file-level lock on the cache directory during flush to prevent conflicts if multiple agents are flushing simultaneously. Flushes are fast (<10ms per memory), so contention is minimal.

## Usage examples

### Add a memory when Scout is running

```
# Agent decides to remember an API design decision
# 1. Health check passes (HTTP 200)
# 2. POST with category provided
curl -s -X POST "{{SCOUT_API}}/spaces/{{DEFAULT_SPACE}}/memory" \
  -H "Content-Type: application/json" \
  -d '{"title": "Auth middleware pattern", "body": "Use middleware for auth checks...", "category": "api-patterns", "tags": ["auth", "middleware"]}'
# → HTTP 201 with memory object
```

### Add a memory when Scout is not running

```
# 1. Health check fails (connection refused)
# 2. Write cache file: .scout-memories-cache/{uuid}.md
#    with YAML frontmatter + markdown body
# 3. Report to agent: "Scout not running — memory cached locally, will flush when available"
```

### Handle 409 — retry with suggested category

```
# 1. POST without category
# → HTTP 409: {"suggested_categories": ["api-patterns", "architecture", "conventions"]}
# 2. Agent picks a category or asks user
# 3. Retry POST with selected category
# → HTTP 201
```

### Auto-flush on next Scout availability

```
# 1. Scout was down, 3 memories cached in .scout-memories-cache/
# 2. Scout comes back up
# 3. Health check passes → flush all 3 cached files in sorted order
#    - .scout-memories-cache/{uuid1}.md → POST → success → delete
#    - .scout-memories-cache/{uuid2}.md → POST → success → delete
#    - .scout-memories-cache/{uuid3}.md → POST → 409 → rename to .failed
# 4. Add the new memory via API
# 5. Report: "Flushed 2/3 cached memories. 1 failed (no category): {uuid3}.md.failed"
```

## Error handling

### Cache corruption

If a cached file cannot be read or parsed (invalid YAML frontmatter), skip it and log a warning. Do not fail the entire flush operation.

### API 500 during flush

Treat server errors as flush failures. Rename the file to `{id}.md.failed` and keep in cache. The agent can retry on the next invocation.

### Failed memory files

Files ending in `.failed` in the cache directory indicate memories that could not be flushed. These should be reported to the agent for inspection and manual retry.
