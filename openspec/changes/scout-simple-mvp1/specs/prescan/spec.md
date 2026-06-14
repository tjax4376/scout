> **See also:** [code-indexing](../code-indexing/spec.md)

## ADDED Requirements

### Requirement: Prescan filesystem walk
Before indexing, the system SHALL walk the workspace filesystem and collect metrics: file count, total bytes, language breakdown, and estimated index size. The system SHALL display metrics as a table and write them to `.scout/spaces/<space>/prescan.json`.

#### Scenario: Prescan metrics displayed
- **WHEN** setup reaches the prescan step
- **THEN** the user sees a table of file counts, sizes, and language breakdown

#### Scenario: Prescan JSON written
- **WHEN** prescan completes
- **THEN** `prescan.json` exists at `.scout/spaces/<space>/prescan.json` with collected metrics

### Requirement: Disk and RAM capacity gate
The system SHALL estimate disk usage (index + vectors) and RAM usage (index build). The system SHALL check available disk space and available RAM on the host. The system SHALL proceed only if both available resources meet or exceed estimates. Otherwise the system SHALL hard-fail with message `"not enough capacity"`.

#### Scenario: Sufficient capacity proceeds
- **WHEN** estimated disk is 2GB, available disk is 50GB, estimated RAM is 4GB, and available RAM is 16GB
- **THEN** prescan passes the capacity gate and indexing proceeds

#### Scenario: Insufficient disk hard-fails
- **WHEN** estimated disk exceeds available disk space
- **THEN** the system hard-fails with `"not enough capacity"` and does not index

#### Scenario: Insufficient RAM hard-fails
- **WHEN** estimated RAM exceeds available RAM
- **THEN** the system hard-fails with `"not enough capacity"` and does not index

### Requirement: User confirmation after prescan
The system SHALL display prescan metrics and require user confirmation before proceeding to indexing. The system SHALL warn the user about estimated resource usage.

#### Scenario: User must confirm to proceed
- **WHEN** prescan displays metrics
- **THEN** the system prompts user to confirm before indexing begins

### Requirement: Byte cap with force override
The system SHALL enforce a hard stop at user-configured byte cap or 100GB total, whichever is lower. The `--force` flag SHALL bypass the byte cap only. The `--force` flag SHALL NOT bypass the disk/RAM capacity gate.

#### Scenario: Byte cap blocks indexing
- **WHEN** prescan total exceeds 100GB and user does not pass `--force`
- **THEN** indexing is blocked

#### Scenario: Force bypasses byte cap only
- **WHEN** prescan total exceeds 100GB and user passes `--force` but capacity gate passes
- **THEN** indexing proceeds despite byte cap

#### Scenario: Force does not bypass capacity gate
- **WHEN** available RAM is less than estimated RAM and user passes `--force`
- **THEN** the system still hard-fails with `"not enough capacity"`
