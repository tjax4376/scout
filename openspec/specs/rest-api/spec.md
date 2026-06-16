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
