> **See also:** [setup-wizard](../../../scout-unified-setup/specs/setup-wizard/spec.md), [space-config](../space-config/spec.md)

## ADDED Requirements

### Requirement: Embed provider registry
The system SHALL support embed providers: `openrouter` (remote), `lmstudio`, `omlx`, and `unsloth-studio` (local). The system SHALL use the same provider, model, and dimensions for both indexing and query embedding. The system SHALL store provider config in `config.yaml` and API keys in `secrets.yaml`.

#### Scenario: OpenRouter remote provider
- **WHEN** user selects `openrouter` at setup
- **THEN** the system stores API key in `secrets.yaml` and fetches available models from OpenRouter

#### Scenario: Local lmstudio provider
- **WHEN** user selects `lmstudio` at setup
- **THEN** the system scans the user-specified localhost port range and probes `GET /v1/models` to discover the endpoint

### Requirement: Separate embed config from chat LLM
The system SHALL maintain embed provider configuration independently from any chat LLM configuration. The system SHALL warn users that local providers must use embedding/tool models, not chat models.

#### Scenario: Embed warning for local provider
- **WHEN** user selects a local provider (lmstudio, omlx, unsloth-studio)
- **THEN** the system displays a warning that embedding/tool models must be used, not chat models

### Requirement: Interactive setup flow
Setup SHALL follow this sequence: workspace root → provider selection → auth/endpoint configuration → fetch models → filter embed-capable models → user model pick → probe dimensions → prescan → index. Any failure SHALL abort setup with no partial index.

#### Scenario: Complete setup flow
- **WHEN** user runs `scout <space> setup` and completes all prompts successfully
- **THEN** config, secrets, manifest, index.db, and graph.bin are created for the space

#### Scenario: Setup failure aborts cleanly
- **WHEN** embed dimension probe fails during setup
- **THEN** setup aborts and no partial index artifacts are written

### Requirement: Model and dimension probing
The system SHALL probe the selected embed model at setup to determine vector dimensions. The system SHALL store model name and dimensions in config and meta table. A change in provider, model, or dimensions SHALL require reindex.

#### Scenario: Dimensions stored after probe
- **WHEN** setup probes a model returning 768-dimensional embeddings
- **THEN** `config.yaml` stores `dimensions: 768` and index meta table matches

#### Scenario: Model change triggers staleness
- **WHEN** user changes embed model in config after indexing
- **THEN** subsequent searches report `stale: true`

### Requirement: Local endpoint discovery
Local providers SHALL have default port suggestions: lmstudio 1234, omlx 8080, unsloth-studio 8000. Setup SHALL prompt user for a port range to scan on `127.0.0.1`. The system SHALL probe `GET /v1/models` on each candidate port. Manual URL entry SHALL be supported as fallback.

#### Scenario: Port range scan finds endpoint
- **WHEN** user specifies port range 1234–1240 for lmstudio and endpoint responds on 1234
- **THEN** `http://127.0.0.1:1234/v1` is stored as the embed endpoint

#### Scenario: Manual URL fallback
- **WHEN** port scan finds no endpoint and user provides a manual URL
- **THEN** the manual URL is stored and probed for models

### Requirement: Python-only embed execution
Embedding SHALL execute in Python only. Python SHALL call provider HTTP APIs and pass resulting `Vec<f32>` embeddings to Rust via pyo3. Rust SHALL never hold API keys or make embed HTTP calls.

#### Scenario: Rust receives pre-computed embeddings
- **WHEN** indexing a chunk during setup or reindex
- **THEN** Python computes the embedding vector and passes `Vec<f32>` to Rust for sqlite-vec storage

### Requirement: Secrets file permissions
The system SHALL write `secrets.yaml` with file permissions `chmod 600`. The system SHALL gitignore `secrets.yaml`. Environment variable overrides SHALL be supported for CI contexts.

#### Scenario: Secrets file permissions
- **WHEN** setup writes `secrets.yaml`
- **THEN** file permissions are set to owner-read/write only (600)

#### Scenario: Environment override for API key
- **WHEN** `OPENROUTER_API_KEY` environment variable is set
- **THEN** the system uses the env value instead of secrets.yaml for OpenRouter auth
