> **See also:** [rest-api](../rest-api/spec.md), [cli-and-serve](../cli-and-serve/spec.md)

## ADDED Requirements

### Requirement: Ship search_scout skill in repo
The system SHALL include `skills/search_scout/` in the repository. The skill SHALL document how agents call the Scout REST API for code search.

#### Scenario: Skill directory exists in repo
- **WHEN** the repository is cloned
- **THEN** `skills/search_scout/` contains the skill definition files

### Requirement: Agent selection at setup
Setup SHALL prompt the user to select target agent: `cursor`, `pi`, or `opencode`. The system SHALL install the skill only for selected agent(s).

#### Scenario: Cursor agent selected
- **WHEN** user selects `cursor` at setup
- **THEN** the skill is installed to Cursor-specific paths only

### Requirement: Global and project-level install
Setup SHALL offer install targets: global, project, or both. Global install places the skill in the user's home directory. Project install places the skill in the workspace root. The user SHALL choose one or both.

#### Scenario: Global install for Cursor
- **WHEN** user selects global install for Cursor
- **THEN** skill is copied to `~/.cursor/skills/search_scout/`

#### Scenario: Project install for Cursor
- **WHEN** user selects project install for Cursor with workspace root `/home/dev/myapp`
- **THEN** skill is copied to `/home/dev/myapp/.cursor/skills/search_scout/`

#### Scenario: Both global and project install
- **WHEN** user selects both install targets
- **THEN** skill is installed to both global and project paths

### Requirement: Agent-specific install paths
The system SHALL install to these paths per agent:

| Agent | Global | Project |
|-------|--------|---------|
| Cursor | `~/.cursor/skills/search_scout/` | `<root>/.cursor/skills/search_scout/` |
| Pi | `~/.pi/skills/search_scout/` | `<root>/.pi/skills/search_scout/` |
| OpenCode | `~/.config/opencode/skills/search_scout/` | `<root>/.opencode/skills/search_scout/` |

#### Scenario: Pi global path
- **WHEN** user selects Pi with global install
- **THEN** skill is at `~/.pi/skills/search_scout/`

#### Scenario: OpenCode project path
- **WHEN** user selects OpenCode with project install at `/proj`
- **THEN** skill is at `/proj/.opencode/skills/search_scout/`

### Requirement: Inject scout_api and default_space
The installed skill SHALL have `scout_api` (base URL with port) and `default_space` injected from setup configuration. The same skill template SHALL be used for all agents with per-target injection.

#### Scenario: API URL injected
- **WHEN** setup completes with API port 8741
- **THEN** installed skill contains `scout_api` pointing to `http://127.0.0.1:8741/v1`

#### Scenario: Default space injected
- **WHEN** setup completes for space `myapp`
- **THEN** installed skill contains `default_space: myapp`

### Requirement: Overwrite protection
The system SHALL NOT overwrite an existing skill installation unless `--force` is passed. Without `--force`, the system SHALL warn and skip if skill already exists at target path.

#### Scenario: Existing skill not overwritten
- **WHEN** skill already exists at target path and setup runs without `--force`
- **THEN** the system warns and skips installation at that path

#### Scenario: Force overwrites existing skill
- **WHEN** skill already exists and setup runs with `--force`
- **THEN** the existing skill is replaced with the new installation
