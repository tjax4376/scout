## ADDED Requirements

### Requirement: Named workspace spaces
The system SHALL support named spaces as aliases mapping to workspace root paths. Each space SHALL have isolated state under `.scout/spaces/<name>/`. Multiple spaces MAY be configured simultaneously.

#### Scenario: Space alias maps to root path
- **WHEN** user creates space `myapp` pointing to `/home/dev/myapp`
- **THEN** all indexing and search for `myapp` operates on `/home/dev/myapp`

#### Scenario: Multiple spaces isolated
- **WHEN** spaces `app1` and `app2` are configured with different root paths
- **THEN** each has separate `index.db`, `manifest.json`, and `graph.bin` with no cross-contamination

### Requirement: Global config layout
The system SHALL store global configuration at `.scout/config.yaml` containing API port, space registry, and embed provider/model/endpoint/dimensions. The system SHALL store secrets at `.scout/secrets.yaml`. The system SHALL store serve PID at `.scout/scout.pid`.

#### Scenario: Config created on setup
- **WHEN** first space setup completes
- **THEN** `.scout/config.yaml` exists with space entry, embed config, and API port

#### Scenario: Secrets separated from config
- **WHEN** user configures OpenRouter
- **THEN** API key is in `secrets.yaml` and provider/model/endpoint are in `config.yaml`

### Requirement: Per-space storage layout
Each space SHALL have storage at:
- `.scout/spaces/<space>/config.yaml` — workspace root path and optional skip rules
- `.scout/spaces/<space>/index.db` — sqlite-vec database
- `.scout/spaces/<space>/manifest.json` — staleness tracking
- `.scout/spaces/<space>/prescan.json` — prescan metrics
- `.scout/cache/<space>/graph.bin` — serialized petgraph

#### Scenario: Per-space artifacts created on index
- **WHEN** space `myapp` is indexed successfully
- **THEN** all per-space artifacts exist at their designated paths

### Requirement: Environment variable overrides
The system SHALL support environment variable overrides for secrets to enable CI usage without secrets files.

#### Scenario: CI env override
- **WHEN** `OPENROUTER_API_KEY` is set in environment
- **THEN** the system uses the environment value and does not require `secrets.yaml` for that key

### Requirement: PyPI distribution
The system SHALL be distributed via PyPI as package `scout` installable via `pipx install scout`. The Rust core SHALL be distributed as `scout_core` maturin wheels for multi-platform targets.

#### Scenario: Pipx install
- **WHEN** user runs `pipx install scout`
- **THEN** the `scout` CLI is available with `scout_core` binary wheel installed
