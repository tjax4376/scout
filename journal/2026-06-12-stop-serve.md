# Journal — scout stop-serve

**Date:** 2026-06-12  
**Metadata:** v0.1.0 | Scout Contributors | stop-serve CLI

## Context

`scout serve` writes PID lock at `.scout/scout.pid` but had no companion stop command. Users killing processes manually risk wrong PID or stale lock files.

## Discussion points

- SIGTERM with 5s poll, then SIGKILL — no HTTP shutdown endpoint
- Missing/stale PID: remove lock file, exit 0
- Failed stop after SIGKILL: keep PID file, exit 1
- `scout_home()` resolution (cwd-first) matches serve

## Code changed

| Area | Files |
|------|-------|
| Lifecycle | `scout/serve/lifecycle.py`, `scout/serve/__init__.py` |
| CLI | `scout/cli/main.py` — `scout stop-serve` handler + usage |
| Tests | `tests/test_stop_serve.py` |
| Docs | `README.md`, `.memory/cards.md` |
| OpenSpec | `openspec/changes/scout-stop-serve/` |

## Test plan

- Missing PID → not_running
- Stale/invalid PID file → stale_removed, file deleted
- Live subprocess → stopped, file deleted
- SIGKILL fallback (mocked)
- Failure leaves PID file
- CLI wires scout_home + exit code 1 on failure
