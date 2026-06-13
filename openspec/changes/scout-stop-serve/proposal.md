## Why

`scout serve` runs as a foreground process with a PID lock at `.scout/scout.pid`, but there is no CLI way to stop it. Users must find and kill the process manually, which is error-prone when the API runs on a custom host/port or when multiple terminal sessions are open.

## What Changes

- Add `scout stop-serve` CLI command to gracefully shut down the running `scout serve` process
- Read PID from `.scout/scout.pid`, send SIGTERM, wait briefly, remove lock file on success
- Handle edge cases: no PID file, stale PID, process already dead, permission denied
- Update CLI usage/help text

## Capabilities

### New Capabilities

<!-- None — behavior extends existing serve lifecycle -->

### Modified Capabilities

- `cli-and-serve`: Add `scout stop-serve` requirement; PID lock cleanup on stop; error scenarios when serve not running

## Impact

- `scout/cli/main.py` — new `stop-serve` command handler
- New helper module or function for PID-based shutdown (e.g. `scout/serve/lifecycle.py`)
- `scout/config.py` — reuse `pid_path`, `scout_home`
- Tests for stop-serve success, stale PID, missing PID
- README CLI reference update
