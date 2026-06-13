## ADDED Requirements

### Requirement: CLI commands
The system SHALL provide CLI commands: `scout <space> setup`, `scout <space> reindex`, `scout <space> search`, and `scout serve`. Setup SHALL run the interactive configuration and initial index flow. Reindex SHALL trigger a full synchronous rebuild. Search SHALL execute vector search and print results.

#### Scenario: Setup creates space and index
- **WHEN** user runs `scout myapp setup` and completes the interactive flow
- **THEN** space `myapp` is configured and fully indexed

#### Scenario: CLI search without serve
- **WHEN** user runs `scout myapp search "auth handler"` without `scout serve` running
- **THEN** search executes successfully via pyo3 direct call

#### Scenario: Reindex rebuilds index
- **WHEN** user runs `scout myapp reindex`
- **THEN** the system performs a full synchronous rebuild and blocks until complete

### Requirement: CLI uses pyo3 direct calls
CLI commands (`setup`, `reindex`, `search`) SHALL call Rust `scout-core` via pyo3 bindings directly. The CLI SHALL NOT route through HTTP even if `scout serve` is running.

#### Scenario: CLI bypasses HTTP when serve is running
- **WHEN** `scout serve` is running and user runs `scout myapp search "query"`
- **THEN** the CLI uses pyo3 direct call, not HTTP to localhost

### Requirement: Scout serve manual foreground process
`scout serve` SHALL run as a manual foreground process. The system SHALL NOT auto-start serve as a daemon or via systemd. The system SHALL write a PID lock file at `.scout/scout.pid`. Only one serve instance SHALL run at a time.

#### Scenario: Serve starts and writes PID
- **WHEN** user runs `scout serve`
- **THEN** FastAPI starts in foreground and `.scout/scout.pid` is written

#### Scenario: Second serve instance rejected
- **WHEN** `scout serve` is already running and user attempts another `scout serve`
- **THEN** the system refuses to start and reports the existing PID

### Requirement: API port scan
The system SHALL scan for an available localhost port starting from 8741 for the Scout API. The selected port SHALL be stored in `config.yaml`.

#### Scenario: Port assigned on first setup
- **WHEN** setup runs and port 8741 is available
- **THEN** Scout API port 8741 is stored in config

#### Scenario: Port incremented when occupied
- **WHEN** port 8741 is in use during setup
- **THEN** the system scans upward until an available port is found and stored

### Requirement: One serve for all spaces
A single `scout serve` process SHALL handle all spaces configured in `config.yaml` on one port with one PID lock file.

#### Scenario: Multiple spaces served
- **WHEN** config.yaml defines spaces `app1` and `app2` and serve is running
- **THEN** both spaces are accessible via `/v1/spaces/app1/...` and `/v1/spaces/app2/...` on the same port
