## 1. Serve lifecycle module

- [x] 1.1 Create `scout/serve/lifecycle.py` with `stop_serve(home: Path)` — read PID, SIGTERM, poll 5s, SIGKILL fallback, remove PID file
- [x] 1.2 Handle edge cases: missing PID file (exit 0), stale PID (remove file, exit 0), ProcessLookupError

## 2. CLI integration

- [x] 2.1 Add `scout stop-serve` handler in `scout/cli/main.py`
- [x] 2.2 Update `_usage()` help text and README CLI reference

## 3. Tests

- [x] 3.1 Unit tests for `stop_serve`: running process stopped, missing PID, stale PID
- [x] 3.2 CLI test: `scout stop-serve` invokes lifecycle with correct scout home

## 4. Docs

- [x] 4.1 Update `.memory/cards.md` with stop-serve behavior
- [x] 4.2 Journal entry for stop-serve change
