# graph-visualizer Specification

## Purpose
TBD - created by archiving change graph-visualization-webpage. Update Purpose after archive.
## Requirements
### Requirement: Graph visualization page
The system SHALL serve a browser-accessible graph visualization page at `/graph` when `scout serve` is running. The page SHALL be reachable on the same host and port as the Scout API without additional setup.

#### Scenario: Graph page loads
- **WHEN** user navigates to `http://127.0.0.1:<port>/graph` while `scout serve` is running
- **THEN** the system returns an HTML page that initializes the graph viewer

#### Scenario: Graph page unavailable when serve stopped
- **WHEN** `scout serve` is not running
- **THEN** `http://127.0.0.1:<port>/graph` is not reachable

### Requirement: Space selection
The graph visualization page SHALL list configured spaces from `GET /v1/spaces/list` and allow the user to select which space to explore.

#### Scenario: Space picker populated
- **WHEN** the graph page loads and the API is healthy
- **THEN** the UI displays all configured space names and defaults to a selectable space

#### Scenario: No spaces configured
- **WHEN** `GET /v1/spaces/list` returns an empty list
- **THEN** the UI displays a message directing the user to run `scout <space> setup`

### Requirement: Symbol search in UI
The graph visualization page SHALL allow users to search for symbols or functions by name within the selected space. Search SHALL use `GET /v1/spaces/{space}/graph/search`.

#### Scenario: Symbol search shows hits
- **WHEN** user enters a symbol name that exists in the indexed graph
- **THEN** the UI displays ranked hits with symbol name, kind, and `rel_path`

#### Scenario: Symbol search selects hit on graph
- **WHEN** user selects a search hit
- **THEN** the UI centers the graph on that node and highlights connected edges

### Requirement: File-centric exploration
The graph visualization page SHALL allow users to locate a file and display all symbols defined in that file plus connected functions from the graph.

#### Scenario: File search lists symbols
- **WHEN** user specifies or selects `rel_path` for an indexed file
- **THEN** the UI displays all symbol nodes in that file from the graph index

#### Scenario: File view shows connected functions
- **WHEN** file symbols are displayed
- **THEN** the UI shows neighbor nodes representing functions or symbols connected via graph edges (imports, calls, contains)

### Requirement: Interactive graph canvas
The graph visualization page SHALL render an interactive graph canvas. Users SHALL be able to pan, zoom, and click nodes to expand neighbors via `GET /v1/spaces/{space}/node/{node_id}/neighbors`.

#### Scenario: Click expands neighbors
- **WHEN** user clicks a node on the graph canvas
- **THEN** the UI fetches neighbors and merges new nodes and edges into the canvas without a full page reload

#### Scenario: Node kind styling
- **WHEN** nodes are rendered on the canvas
- **THEN** file, function, and other kinds are visually distinguishable

### Requirement: Source preview panel
The graph visualization page SHALL display node metadata including `location_ref` and line range. Users SHALL be able to preview source text via `GET /v1/spaces/{space}/file`.

#### Scenario: Node click shows metadata
- **WHEN** user selects a node with `location_ref`
- **THEN** the side panel shows symbol name, kind, path, and line range

#### Scenario: Source preview loads
- **WHEN** user requests source preview for a node with a valid `rel_path`
- **THEN** the UI fetches and displays file text (or line slice when line range is known)

### Requirement: Deep-link query parameters
The graph visualization page SHALL support URL query parameters `space`, `file`, and `q` to restore viewer state on load.

#### Scenario: Deep link opens file view
- **WHEN** user opens `/graph?space=myapp&file=src/auth.py`
- **THEN** the UI selects space `myapp` and loads the file-centric graph view

#### Scenario: Deep link runs symbol search
- **WHEN** user opens `/graph?space=myapp&q=authenticate`
- **THEN** the UI selects space `myapp` and runs symbol search for `authenticate`

