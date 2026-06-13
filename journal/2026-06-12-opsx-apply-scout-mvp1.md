# Journal: OpenSpec Apply — Scout Simple MVP1

**Date:** 2026-06-12
**Author:** Cursor Agent
**Version:** 1.0

## Context

User ran `/opsx-apply` on change `scout-simple-mvp1` — implement 88 tasks from grill-closed MVP1 scope. Greenfield build: Rust `scout_core` + Python shell via pyo3/maturin.

## Discussion Points

- Built full module structure at repo root: `scout_core/`, `scout/`, `skills/search_scout/`
- Rust: scan, tree-sitter parse (TS/JS, Py, Rust, Go), petgraph, sqlite-vec, search, neighbors, staleness
- Python: config, CLI (`scout <space> setup|reindex|search`, `scout serve`), FastAPI REST, embed providers, prescan, skill install
- pyo3 0.24 + `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` for Python 3.14
- `maturin develop` verified in `.venv`; 8 pytest + 2 cargo tests pass
- Remaining: PyPI publish workflow (16.2), pipx clean-machine verify (16.3)

## Code Changed

| Area | Files | Summary |
|------|-------|---------|
| Rust core | `scout_core/src/*` | Engine: scan, parse, chunk, graph, index, search, staleness, pyapi |
| Python | `scout/*.py` | config, cli, api, embed, prescan, skill, indexing |
| Skill | `skills/search_scout/SKILL.md` | Agent skill template |
| Build | `Cargo.toml`, `pyproject.toml`, `.github/workflows/ci.yml` | Workspace, maturin, CI |
| Tests | `tests/test_integration.py` | 8 integration tests |
| Config | `.gitignore`, `README.md` | Dev setup docs |

## Summary

86/88 tasks complete. MVP1 codebase functional locally via `maturin develop`. Archive after PyPI/pipx distribution tasks.
