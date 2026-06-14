> **See also:** [cli-and-serve](../../../scout-simple-mvp1/specs/cli-and-serve/spec.md)

## MODIFIED Requirements

### Requirement: CLI commands
The system SHALL provide CLI commands: `scout <space> setup`, `scout <space> reindex`, `scout <space> search`, `scout serve`, and `scout stop-serve`. Setup SHALL run the interactive configuration and initial index flow. Reindex SHALL trigger a full synchronous rebuild. Search SHALL execute vector search and print results. Stop-serve SHALL shut down the running serve process.

#### Scenario: Setup creates space and index
- **WHEN** user runs `scout myapp setup` and completes the interactive flow
- **THEN** space `myapp` is configured and fully indexed

#### Scenario: CLI search without serve
- **WHEN** user runs `scout myapp search "auth handler"` without `scout serve` running
- **THEN** search executes successfully via pyo3 direct call

#### Scenario: Reindex rebuilds index
- **WHEN** user runs `scout myapp reindex`
- **THEN** the system performs a full synchronous rebuild and blocks until complete

#### Scenario: Stop-serve shuts down running process
- **WHEN** `scout serve` is running and user runs `scout stop-serve`
- **THEN** the serve process terminates and `.scout/scout.pid` is removed

## ADDED Requirements

### Requirement: Scout stop-serve command
The system SHALL provide `scout stop-serve` to stop the `scout serve` process identified by `.scout/scout.pid`. The command SHALL resolve `.scout/` using the same cwd-first then home lookup as other CLI commands.

#### Scenario: Stop running serve
- **WHEN** `.scout/scout.pid` contains a valid PID for a running `scout serve` process
- **THEN** the system sends SIGTERM, waits for exit (up to 5 seconds), removes the PID file, and reports success

#### Scenario: No serve running
- **WHEN** `.scout/scout.pid` does not exist
- **THEN** the system reports that serve is not running and exits with code 0

#### Scenario: Stale PID file
- **WHEN** `.scout/scout.pid` exists but the PID is not a running process
- **THEN** the system removes the stale PID file and reports that serve was not running

#### Scenario: Stop fails after SIGKILL
- **WHEN** the process survives SIGTERM and SIGKILL
- **THEN** the system reports failure and leaves the PID file in place
