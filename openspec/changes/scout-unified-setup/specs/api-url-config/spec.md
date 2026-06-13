## ADDED Requirements

### Requirement: api_base_url persistence
The system SHALL store `api_base_url` in `config.yaml` as the canonical Scout REST API base URL (e.g. `http://127.0.0.1:8741/v1`).

#### Scenario: URL saved on setup
- **WHEN** user enters `http://10.0.0.5:9000/v1` at setup
- **THEN** `config.yaml` contains `api_base_url: http://10.0.0.5:9000/v1`

#### Scenario: Migration from api_port only
- **WHEN** config has `api_port: 8741` but no `api_base_url`
- **THEN** load synthesizes `http://127.0.0.1:8741/v1`

### Requirement: Serve binds from api_base_url
`scout serve` SHALL bind host and port parsed from `api_base_url`, not hardcoded localhost.

#### Scenario: Custom host serve
- **WHEN** `api_base_url` is `http://192.168.1.10:8741/v1`
- **THEN** uvicorn binds to host `192.168.1.10` port `8741`

### Requirement: Port conflict scan on configured host
If the configured port is in use on the configured host during setup, the system SHALL scan upward in the 8741–8799 range and update `api_base_url` accordingly.

#### Scenario: Port 8741 busy
- **WHEN** port 8741 is in use on the configured host during setup
- **THEN** system assigns next free port and updates `api_base_url`
