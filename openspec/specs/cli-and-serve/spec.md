# cli-and-serve Specification

## Purpose
TBD - created by archiving change graph-visualization-webpage. Update Purpose after archive.
## Requirements
### Requirement: Graph UI URL on serve start
When `scout serve` starts successfully, the system SHALL log the graph visualization URL in the startup banner.

#### Scenario: Serve banner includes graph URL
- **WHEN** user runs `scout serve` and the API binds to port 8747
- **THEN** stdout includes a line with `http://127.0.0.1:8747/graph`

### Requirement: Graph static assets in package
The Python package SHALL include graph visualization static files so `pip install` and wheel distribution serve `/graph` without a separate asset download step.

#### Scenario: Wheel contains graph assets
- **WHEN** package wheel is built
- **THEN** `scout/web/graph/` files are included in the installed package
