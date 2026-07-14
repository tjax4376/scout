# rest-api Specification

## Purpose

Canonical REST API contract for Scout `scout serve`. Kept in sync with `api-contracts.md` and `scout/api/app.py`.

## Requirements

### Requirement: Health endpoint
The system SHALL expose `GET /v1/health` returning liveness status.

#### Scenario: Health check
- **WHEN** client sends `GET /v1/health`
- **THEN** the system returns HTTP 200 with `{"status": "ok"}`

### Requirement: List spaces endpoint
The system SHALL expose `GET /v1/spaces/list` returning configured spaces from `config.yaml`.

#### Scenario: List configured spaces
- **WHEN** client sends `GET /v1/spaces/list`
- **THEN** the system returns a JSON object with a `spaces` array

### Requirement: Vector search endpoint
The system SHALL expose `POST /v1/spaces/{space}/search` accepting JSON with `query` (required) and optional filters. When no vector index exists, the system SHALL return HTTP 503.

#### Scenario: Search request
- **WHEN** client sends `POST /v1/spaces/{space}/search` with a valid query body
- **THEN** the system returns ranked hits or HTTP 503 when no index is available

### Requirement: Node lookup endpoint
The system SHALL expose `GET /v1/spaces/{space}/node/{node_id}` returning node metadata and content.

#### Scenario: Node lookup
- **WHEN** client sends `GET /v1/spaces/{space}/node/{node_id}` for an existing node
- **THEN** the system returns node metadata and text

### Requirement: Graph neighbors endpoint
The system SHALL expose `GET /v1/spaces/{space}/node/{node_id}/neighbors` for graph expansion without embed.

#### Scenario: Neighbor expansion
- **WHEN** client sends `GET /v1/spaces/{space}/node/{node_id}/neighbors`
- **THEN** the system returns connected graph nodes and edges

### Requirement: Symbols list endpoint
The system SHALL expose `GET /v1/spaces/{space}/symbols` listing graph symbol nodes under an optional `path_prefix`.

#### Scenario: Symbols under prefix
- **WHEN** client sends `GET /v1/spaces/{space}/symbols?path_prefix=scout/api`
- **THEN** the system returns symbol nodes whose paths match the prefix

### Requirement: Workspace file read endpoint
The system SHALL expose `GET /v1/spaces/{space}/file` reading source files or line ranges from the indexed workspace.

#### Scenario: File read
- **WHEN** client sends `GET /v1/spaces/{space}/file?rel_path=scout/api/app.py`
- **THEN** the system returns file content for the requested path

### Requirement: Graph symbol search endpoint
The system SHALL expose `GET /v1/spaces/{space}/graph/search` accepting query parameter `q` (required) and optional `top_k` (default 10, max 50). The endpoint SHALL match graph nodes by symbol name or `rel_path` without vector embed.

#### Scenario: Symbol name match
- **WHEN** client requests `GET /v1/spaces/{space}/graph/search?q=authenticate` and symbol exists in graph
- **THEN** response includes hits ranked by relevance with matching `node_id` values

#### Scenario: No embed required
- **WHEN** space is graph-only with no `index.db` and serve runs without `--embed`
- **THEN** graph search returns 200 with hits from `graph.bin`

### Requirement: Graph file aggregate endpoint
The system SHALL expose `GET /v1/spaces/{space}/graph/file` accepting required query parameter `rel_path`. The response SHALL include `symbols` and depth-1 `neighbors`.

#### Scenario: File symbols returned
- **WHEN** client requests `GET /v1/spaces/{space}/graph/file?rel_path=scout/api/app.py` for an indexed file
- **THEN** response `symbols` lists all symbol nodes whose `rel_path` matches that file

### Requirement: Session embed status endpoint
The system SHALL expose `GET /v1/spaces/{space}/session/status` when `scout serve --embed` is active.

#### Scenario: Session status
- **WHEN** client calls `GET /v1/spaces/{space}/session/status`
- **THEN** the system returns session embed queue and index statistics

### Requirement: Session index clear endpoint
The system SHALL expose `DELETE /v1/spaces/{space}/session/index` clearing the session vector index.

#### Scenario: Clear session index
- **WHEN** client sends `DELETE /v1/spaces/{space}/session/index`
- **THEN** the system clears the in-memory session vector index

### Requirement: Reindex endpoint
The system SHALL expose `POST /v1/spaces/{space}/reindex` triggering a synchronous full rebuild.

#### Scenario: Reindex via API
- **WHEN** client sends `POST /v1/spaces/{space}/reindex` and no reindex is in progress
- **THEN** the system performs a full synchronous reindex and returns on completion

### Requirement: Graph static assets
The system SHALL serve graph visualization static assets from `/graph` on the same `scout serve` process.

#### Scenario: Static assets served
- **WHEN** client requests `GET /graph/` or `GET /graph/index.html`
- **THEN** the system returns the graph visualization HTML entry point

### Requirement: Create memory endpoint
The system SHALL expose `POST /v1/spaces/{space}/memory` accepting JSON with `title` (required), `body` (required), `tags` (optional array), and `category` (optional). When `category` is omitted, the system SHALL return HTTP 409 with suggested categories. When provided, the system SHALL create a memory file and return HTTP 201 with the memory object.

#### Scenario: Create memory with category
- **WHEN** client sends `POST /v1/spaces/{space}/memory` with `title`, `body`, and `category`
- **THEN** the system returns HTTP 201 with the created memory object

#### Scenario: Create memory without category
- **WHEN** client sends `POST /v1/spaces/{space}/memory` without `category`
- **THEN** the system returns HTTP 409 with `suggested_categories` array

### Requirement: Get memory endpoint
The system SHALL expose `GET /v1/spaces/{space}/memory/{memory_id}` returning the full memory object for an existing memory.

#### Scenario: Get existing memory
- **WHEN** client sends `GET /v1/spaces/{space}/memory/{memory_id}` for a valid ID
- **THEN** the system returns HTTP 200 with the memory object

#### Scenario: Get non-existent memory
- **WHEN** client sends `GET /v1/spaces/{space}/memory/{memory_id}` for an unknown ID
- **THEN** the system returns HTTP 404

### Requirement: List memories endpoint
The system SHALL expose `GET /v1/spaces/{space}/memories` with optional query parameters `category`, `tag` (repeatable), and `q` (full-text search). The response SHALL include a `memories` array and `total` count.

#### Scenario: List all memories
- **WHEN** client sends `GET /v1/spaces/{space}/memories` with no filters
- **THEN** the system returns HTTP 200 with a `memories` array and `total` count

#### Scenario: Filter by category
- **WHEN** client sends `GET /v1/spaces/{space}/memories?category=api`
- **THEN** the system returns only memories matching the category

### Requirement: Ask memory endpoint
The system SHALL expose `POST /v1/spaces/{space}/memory/ask` accepting JSON with `query` (required, string, min 1 char, max 5000 chars). The endpoint SHALL search the space's memory store and return the most relevant memories as context. Returns HTTP 200 with `memories` array, `total` count, and echoed `query`. Returns HTTP 400 for empty query, HTTP 404 for unknown space.

#### Scenario: Ask with query returns relevant memories
- **WHEN** client sends `POST /v1/spaces/{space}/memory/ask` with `{"query": "user preferences for code style"}`
- **THEN** the system returns HTTP 200 with a `memories` array containing matching memories and a `total` count

#### Scenario: Ask with empty query returns error
- **WHEN** client sends `POST /v1/spaces/{space}/memory/ask` with `{"query": ""}`
- **THEN** the system returns HTTP 400 with an error detail

#### Scenario: Ask with no matching memories
- **WHEN** client sends `POST /v1/spaces/{space}/memory/ask` with a query that matches no memories
- **THEN** the system returns HTTP 200 with an empty `memories` array and `total: 0`

#### Scenario: Ask on unknown space
- **WHEN** client sends `POST /v1/spaces/{space}/memory/ask` for a space not in config
- **THEN** the system returns HTTP 404

### Requirement: Ask structure endpoint
The system SHALL expose `POST /v1/spaces/{space}/ask` accepting JSON with `query` (required, string, min 1 char, max 5000 chars) and optional `top_k`, `expand_depth`, `max_nodes`, and `path_prefix`. The endpoint SHALL resolve the query against the space graph index without embed or LLM processing and return compact structure hits (and optional edges) suitable for agent context. Full source content SHALL NOT be included in the ask response. Returns HTTP 200 on success, HTTP 400 for invalid input, HTTP 404 for unknown space or missing graph. Shares the search per-minute rate-limit bucket.

#### Scenario: Successful structure ask
- **WHEN** client sends `POST /v1/spaces/{space}/ask` with a valid non-empty `query` and the graph index contains matches
- **THEN** the system returns HTTP 200 with `hits`, `total`, echoed `query`, and `mode` `"graph"`

#### Scenario: Ask does not require vector index
- **WHEN** client calls ask while serve is graph-only without `--embed`
- **THEN** the system returns structure results from the graph (HTTP 200) rather than HTTP 503

#### Scenario: Invalid ask query
- **WHEN** client sends ask with empty or oversize `query`
- **THEN** the system returns HTTP 400
