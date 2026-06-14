# Scout build script

**Context:** Need local dev helper to build scout binaries and start API without memorizing maturin/venv steps.

**Discussion points:**
- Scout ships Rust `scout_core` via maturin + Python CLI; dev flow is `maturin develop --release` into `.venv`
- Production flow mirrors PyPI/pipx: `maturin build --release` wheel → install into isolated `.venv-prod`
- Python 3.14 requires `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` at build time
- `scout serve` is foreground API; dev and production use separate venvs
- Script subcommands: `build dev`, `build production`, `start`, `start production` (`prod` alias)

**Code changed:**
- Added `scripts/scout.sh` — dev: `.venv` + `maturin develop`; production: `dist/` wheel + `.venv-prod` pip install; `start` / `start production` exec `scout serve` from matching venv

**Test plan:**
- `bash scripts/scout.sh build dev` — venv + maturin develop succeeds, `import scout_core` works
- `bash scripts/scout.sh build production` — wheel in `dist/`, installed to `.venv-prod`, `import scout_core` works
- `bash scripts/scout.sh start` / `start production` — binds API from correct venv
- `bash scripts/scout.sh` / unknown args — prints usage, exit 1
- `start` without prior build — clear error pointing to matching `build` command
