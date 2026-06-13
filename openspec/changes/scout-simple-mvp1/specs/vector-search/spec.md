## ADDED Requirements

### Requirement: Vector-only search
The system SHALL perform vector similarity search against sqlite-vec embeddings. The system SHALL NOT implement hybrid FTS or keyword search in MVP1. Search SHALL require a `query` string. Optional parameters: `top_k` (default 10), `min_score` (default 0.0), `kinds[]` (exact kind filter), `path_prefix` (path prefix filter). The system SHALL NOT support pagination.

#### Scenario: Basic vector search
- **WHEN** user submits `query: "authentication middleware"` with default parameters
- **THEN** the system returns up to 10 results ranked by vector similarity score

#### Scenario: Kind filter applied
- **WHEN** user submits `query: "parse config"` with `kinds: ["function"]`
- **THEN** only nodes with kind `function` appear in results

#### Scenario: Path prefix filter applied
- **WHEN** user submits `query: "handler"` with `path_prefix: "src/api/"`
- **THEN** only nodes under `src/api/` appear in results

#### Scenario: Minimum score threshold
- **WHEN** user submits `min_score: 0.5` and some hits score below 0.5
- **THEN** those hits are excluded from results

### Requirement: Search hit response format
Each search hit SHALL include node metadata (node_id, kind, symbol, path, start_line, end_line, score), a `snippet` of approximately 500 characters, a `breadcrumb` showing containment hierarchy, and a nested `neighbors` array.

#### Scenario: Hit includes snippet and breadcrumb
- **WHEN** a search returns a function symbol hit
- **THEN** the hit includes a ~500 char code snippet and breadcrumb like `src/ > api/ > handlers.ts > handleAuth`

### Requirement: Neighbor traversal via anchor pivot
The system SHALL use the search hit as the anchor. The system SHALL traverse up 1 node via `contains` edge to find the pivot (parent). The system SHALL traverse down from the pivot using BFS with depth ≤ 3 via `contains`, `imports`, and `calls` edges. The system SHALL cap neighbors at 20 nodes, deduplicate, and exclude the anchor from neighbors. Each neighbor SHALL include `edge` type and `depth` (1–3).

#### Scenario: Up 1 to parent file
- **WHEN** anchor is a function symbol inside `handlers.ts`
- **THEN** pivot is the `handlers.ts` file node (parent via `contains`)

#### Scenario: Down 3 BFS from pivot
- **WHEN** pivot is a file node with imports and contained symbols
- **THEN** neighbors include related symbols and imported modules up to depth 3 from pivot

#### Scenario: Neighbor cap enforced
- **WHEN** BFS discovers more than 20 neighbor nodes
- **THEN** the system returns at most 20 neighbors

#### Scenario: Anchor excluded from neighbors
- **WHEN** neighbor traversal completes
- **THEN** the anchor node itself is not included in the neighbors array

### Requirement: Staleness in search response
The search response SHALL include a top-level `stale` boolean and `index_version` string. When stale, the system SHALL still return search results.

#### Scenario: Stale index returns results
- **WHEN** manifest detects changed files and search is executed
- **THEN** response includes `stale: true` and valid search results

#### Scenario: Fresh index
- **WHEN** manifest matches filesystem and embed config
- **THEN** response includes `stale: false`

### Requirement: Node lookup without search
The system SHALL provide full chunk retrieval by `node_id` without similarity score. This endpoint SHALL return the complete stored text for the node.

#### Scenario: Full chunk retrieval
- **WHEN** user requests `GET /node/{node_id}` for an existing node
- **THEN** the system returns the full chunk text and node metadata without a score field
