> **See also:** [rest-api](../../../scout-simple-mvp1/specs/rest-api/spec.md), [agent-skill](../../../scout-simple-mvp1/specs/agent-skill/spec.md)

## ADDED Requirements

### Requirement: Ship code-reviewer-scout skill in repo
The system SHALL include `skills/code-reviewer-scout/` in the repository. The skill SHALL document a token-efficient code review workflow using the Scout REST API. The skill SHALL NOT modify or replace `skills/search_scout/`. The skill frontmatter `name` and all agent install directory names SHALL use hyphens only (no underscores).

#### Scenario: Skill directory exists in repo
- **WHEN** the repository is cloned
- **THEN** `skills/code-reviewer-scout/` contains `SKILL.md`, `README.md`, and helper script(s)

#### Scenario: Skill name uses hyphens only
- **WHEN** an agent reads `SKILL.md` frontmatter
- **THEN** `name` is `code-reviewer-scout` (hyphens, no underscores)

#### Scenario: Review workflow documented
- **WHEN** an agent reads the installed `SKILL.md`
- **THEN** it describes search-first review with path scoping, snippet use, node expansion, and full-file read as last resort

### Requirement: Standalone install module
The system SHALL provide `scout/code_reviewer/` as a standalone install module. The module SHALL NOT modify `scout/skill/install.py` or the setup wizard.

#### Scenario: Install module exists
- **WHEN** the repository is built
- **THEN** `scout/code_reviewer/install.py` exposes install logic for the code reviewer skill

#### Scenario: Existing search_scout install unchanged
- **WHEN** code reviewer skill is installed
- **THEN** `scout/skill/install.py` and setup wizard behavior remain unchanged

### Requirement: Agent-specific install paths
The install module SHALL support Cursor, Pi, and OpenCode with these paths:

| Agent | Global | Project |
|-------|--------|---------|
| Cursor | `~/.cursor/skills/code-reviewer-scout/` | `<root>/.cursor/skills/code-reviewer-scout/` |
| Pi | `~/.pi/skills/code-reviewer-scout/` | `<root>/.pi/skills/code-reviewer-scout/` |
| OpenCode | `~/.config/opencode/skills/code-reviewer-scout/` | `<root>/.opencode/skills/code-reviewer-scout/` |

#### Scenario: Cursor project install
- **WHEN** user installs for Cursor at project root `/proj`
- **THEN** skill is copied to `/proj/.cursor/skills/code-reviewer-scout/`

#### Scenario: All agents use hyphenated directory name
- **WHEN** user installs for any supported agent
- **THEN** the install directory name is `code-reviewer-scout` (hyphens only)

### Requirement: Inject scout_api and default_space
The installed skill SHALL have `scout_api` (base URL with `/v1`) and `default_space` injected from install arguments or environment. The same skill template SHALL be used for all agents with per-target injection.

#### Scenario: API URL injected
- **WHEN** install completes with API base `http://127.0.0.1:8741/v1`
- **THEN** installed `SKILL.md` contains that URL in place of template placeholders

#### Scenario: Default space injected
- **WHEN** install completes for space `myapp`
- **THEN** installed `SKILL.md` contains `default_space: myapp`

### Requirement: Overwrite protection
The install module SHALL NOT overwrite an existing skill installation unless `--force` is passed. Without `--force`, the system SHALL raise or report clearly when skill already exists at target path.

#### Scenario: Existing skill not overwritten
- **WHEN** skill already exists at target path and install runs without `--force`
- **THEN** the system refuses to overwrite and reports the existing path

#### Scenario: Force overwrites existing skill
- **WHEN** skill already exists and install runs with `--force`
- **THEN** the existing skill is replaced with a fresh copy from template

### Requirement: Review helper script uses REST only
The skill SHALL include a helper script callable from agent terminals. The script SHALL call existing Scout REST endpoints only (`GET /health`, `GET /spaces/list`, `POST /spaces/{space}/search`, `GET /spaces/{space}/node/{node_id}`). The script SHALL support path-scoped search via `path_prefix` and optional `kinds` filter.

#### Scenario: Path-scoped search
- **WHEN** user runs the helper with space, query, and path prefix `src/api/`
- **THEN** the script sends `POST /search` with `path_prefix` set and prints JSON results

#### Scenario: Node lookup after search
- **WHEN** user runs the helper with space and node_id from a search hit
- **THEN** the script sends `GET /node/{node_id}` and prints the node payload

### Requirement: No Scout core behavior changes
This capability SHALL NOT add, remove, or modify requirements for Scout REST API routes, CLI commands, indexing, embed providers, or the `search_scout` agent skill.

#### Scenario: API contract unchanged
- **WHEN** code reviewer skill is shipped
- **THEN** no new REST routes are added and existing route behavior is unchanged

#### Scenario: Setup wizard unchanged
- **WHEN** user runs `scout <space> setup`
- **THEN** the wizard does not automatically install or reference `code-reviewer-scout` unless a separate future change adds that

### Requirement: Tests for code reviewer skill
The system SHALL include pytest coverage for skill template presence, install path resolution, config injection, and overwrite protection.

#### Scenario: Install test passes
- **WHEN** pytest runs `tests/code_reviewer/`
- **THEN** install to a temp directory succeeds and injected placeholders are replaced
