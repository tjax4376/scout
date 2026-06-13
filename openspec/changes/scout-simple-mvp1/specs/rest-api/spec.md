## ADDED Requirements

### Requirement: Localhost REST API at /v1
The system SHALL expose a FastAPI REST API bound to localhost only. The API SHALL be versioned under `/v1`. The API SHALL provide an OpenAPI specification. The API SHALL NOT require authentication in MVP1.

#### Scenario: Health check endpoint
- **WHEN** client sends `GET /v1/health`
- **THEN** the system returns a successful health response

#### Scenario: Localhost bind only
- **WHEN** `scout serve` starts
- **THEN** the API binds to `127.0.0.1` and is not accessible from external network interfaces

### Requirement: Multi-space routing
A single `scout serve` instance SHALL serve all spaces defined in `config.yaml`. Routes SHALL be prefixed with `/v1/spaces/{space}/`. Unknown space names SHALL return 404.

#### Scenario: Search within named space
- **WHEN** client sends `POST /v1/spaces/myapp/search` with valid space `myapp`
- **THEN** search executes against the `myapp` space index

#### Scenario: Unknown space returns 404
- **WHEN** client sends a request to `/v1/spaces/nonexistent/search`
- **THEN** the system returns HTTP 404

### Requirement: Search endpoint
The system SHALL expose `POST /v1/spaces/{space}/search` accepting a JSON body with `query` (required) and optional `top_k`, `min_score`, `kinds`, `path_prefix`. The response SHALL follow the vector-search spec format.

#### Scenario: Valid search request
- **WHEN** client POSTs `{"query": "error handling", "top_k": 5}` to the search endpoint
- **THEN** the system returns up to 5 ranked hits with neighbors

### Requirement: Node lookup endpoint
The system SHALL expose `GET /v1/spaces/{space}/node/{node_id}` returning full chunk content and metadata for the given node.

#### Scenario: Existing node retrieved
- **WHEN** client requests a valid `node_id` in an indexed space
- **THEN** the system returns full chunk text and node metadata

#### Scenario: Unknown node returns 404
- **WHEN** client requests a `node_id` not in the index
- **THEN** the system returns HTTP 404

### Requirement: Reindex endpoint
The system SHALL expose `POST /v1/spaces/{space}/reindex` triggering a synchronous full rebuild. The system SHALL return 409 if reindex is already in progress.

#### Scenario: Reindex via API
- **WHEN** client POSTs to the reindex endpoint and no reindex is in progress
- **THEN** the system performs a full synchronous reindex and returns on completion

#### Scenario: Concurrent reindex returns 409
- **WHEN** a reindex is in progress and client POSTs to reindex
- **THEN** the system returns HTTP 409 Conflict

### Requirement: Response headers for staleness and version
The system SHALL include `X-Scout-Stale` (true/false) and `X-Scout-Index-Version` headers on search and node responses.

#### Scenario: Stale header set
- **WHEN** search executes against a stale index
- **THEN** response includes `X-Scout-Stale: true`

#### Scenario: Index version header present
- **WHEN** any search or node response is returned
- **THEN** response includes `X-Scout-Index-Version` with the current index version identifier
