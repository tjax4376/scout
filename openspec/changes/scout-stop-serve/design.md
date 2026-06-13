## Context

MVP1 introduced `scout serve` as a manual foreground process with PID lock at `.scout/scout.pid`. The serve handler writes the PID on start and removes the lock file in a `finally` block on clean exit. There is no companion command to stop serve from another terminal.

## Goals / Non-Goals

**Goals:**
- `scout stop-serve` stops the process recorded in `.scout/scout.pid`
- Clean up stale PID file when process is already dead
- Clear user-facing messages for all outcomes

**Non-Goals:**
- Daemon/systemd integration
- Remote stop across machines
- HTTP shutdown endpoint on the API

## Decisions

**Decision:** Use OS signals (SIGTERM) via `os.kill(pid, signal.SIGTERM)` rather than an HTTP `/shutdown` endpoint.

**Rationale:** Matches foreground-process model; no API auth needed; works even if API is wedged.

**Alternative considered:** POST `/v1/shutdown` — rejected (adds auth concern, API must be responsive).

**Decision:** Resolve `.scout/` via existing `scout_home()` (cwd-first, then home).

**Rationale:** Consistent with `scout serve` PID file location.

**Decision:** After SIGTERM, poll up to 5s for process exit; if still alive, send SIGKILL.

**Rationale:** uvicorn may need brief graceful shutdown; avoid leaving orphan.

**Decision:** Remove PID file after successful stop or when PID is stale (process not found).

**Rationale:** Unblocks future `scout serve` starts.

**Decision:** New module `scout/serve/lifecycle.py` with `stop_serve(home: Path) -> None`.

**Rationale:** Keeps CLI thin; independently testable.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Stale PID kills wrong process | Verify process exists and optionally match process name/cmdline before kill |
| SIGTERM ignored | Fallback SIGKILL after timeout |
| PID file from different scout install | Use scout_home resolution; document single `.scout/` per machine |

## Migration Plan

No data migration. Ship in next release; document in README CLI reference.

## Open Questions

None — behavior is straightforward.
