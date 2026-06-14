> **See also:** [agent-skill](../../../scout-simple-mvp1/specs/agent-skill/spec.md), [rest-api](../../../scout-simple-mvp1/specs/rest-api/spec.md)

## MODIFIED Requirements

### Requirement: Agent selection at setup
Setup SHALL prompt the user to select target agent: `cursor`, `pi`, or `opencode`. The `--agent` flag SHALL override the interactive prompt for non-interactive use. The system SHALL install the skill after every successful setup.

#### Scenario: Interactive agent selection
- **WHEN** user runs `scout myapp setup` without `--agent`
- **THEN** setup prompts for agent selection before skill install

#### Scenario: Agent flag override
- **WHEN** user runs `scout myapp setup --agent cursor`
- **THEN** setup skips agent prompt and uses `cursor`

### Requirement: Inject scout_api and default_space
The installed skill SHALL have `scout_api` set to `api_base_url` from config and `default_space` set to the space name. Skill install SHALL run on every successful setup.

#### Scenario: Custom API URL injected
- **WHEN** setup completes with `api_base_url` `http://10.0.0.5:9000/v1`
- **THEN** installed skill contains `scout_api` pointing to `http://10.0.0.5:9000/v1`
