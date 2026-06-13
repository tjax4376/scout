## ADDED Requirements

### Requirement: Four-branch setup menu
Setup SHALL present a single menu with four branches combining file source and embed provider:

| Branch | Files | Embed |
|--------|-------|-------|
| 1 | Local path | Local providers (lmstudio, omlx, unsloth-studio) |
| 2 | Local path | openrouter |
| 3 | Git clone (cwd subdir) | Local providers |
| 4 | Git clone (cwd subdir) | openrouter |

#### Scenario: Branch 1 selected
- **WHEN** user selects branch 1
- **THEN** setup prompts for local workspace root and local embed provider

#### Scenario: Branch 4 selected
- **WHEN** user selects branch 4
- **THEN** setup prompts for git URL, clones to cwd subdirectory, and configures OpenRouter

### Requirement: Scout API URL always prompted
Setup SHALL prompt for full Scout API base URL (scheme + host + port + `/v1` path) on every run before branch selection.

#### Scenario: Default URL offered
- **WHEN** setup starts
- **THEN** default URL is `http://127.0.0.1:8741/v1` or existing `api_base_url` from config

### Requirement: Git clone to cwd subdirectory
Branches 3 and 4 SHALL clone the remote repository into a subdirectory of the current working directory.

#### Scenario: Clone succeeds
- **WHEN** user provides valid git URL and subdir name
- **THEN** repository is cloned to `<cwd>/<subdir>` and used as workspace root

#### Scenario: Clone target exists
- **WHEN** target directory exists and is non-empty without `--force`
- **THEN** setup aborts with an error message
