# Journal: pipx scout name collision (wrong package)

## Context

User reported `scout scout reindex` and `scout scout setup` failing with:
`Error: [.../pipx/venvs/scout/.../scout/server.py] only accepts one argument, which is the path to the database file.`

## Discussion

- **Not a regression** in Scout 0.1.0 code — wrong Python package on PATH.
- `pipx list` showed `scout 4.0.0` — legacy Flask/SQLite FTS document search on PyPI, unrelated to this repo.
- That package's CLI: `scout <database_path>` — interprets `scout reindex` as two args → panic.
- Correct Scout 0.1.0 CLI: `scout <space> setup|reindex|search`, entry `scout.cli.main:main`.
- PyPI name collision risk: `pip install scout` / `pipx install scout` may resolve to 4.0.0 (higher version) instead of 0.1.0.

## Code changed

None. Operational fix on user machine:
```bash
pipx uninstall scout
pipx install dist/scout-0.1.0-cp311-abi3-macosx_11_0_arm64.whl
```

## Test plan

- `scout --help` → shows space-based subcommands
- `scout scout reindex` → starts reindex (or prescan/index errors), not server.py panic
- `which scout` → `~/.local/bin/scout` when venv inactive
