# tests

Pytest suite for Scout Python shell and API. Rust unit tests live in `scout_core/` (`cargo test`).

## Layout

```
tests/
  conftest.py           # shared fixtures: sample_project, scout_home, requires_scout_core
  api/                  # FastAPI TestClient — contract tests vs api-contracts.md
  cli/                  # setup wizard, stop-serve, serve bind
  embed/                # embed provider auth headers
  integration/          # config, prescan, skill install, scout_core pipeline
```

## Conventions

| Pattern | Usage |
|---------|-------|
| `test_<endpoint>_<scenario>` | API tests (e.g. `test_spaces_list_empty`) |
| `@requires_scout_core` | Skip when maturin build missing |
| `scout_home` fixture | Isolated `.scout` dir via `bootstrap_scout_dir` |
| `api_client` fixture | Patches `scout.api.app.scout_home`, returns `TestClient` |
| `save_spaces_config()` | Helper in `api/conftest.py` for multi-space API tests |

## Run

```bash
# All tests (scout_core tests skip if not built)
pytest -q

# API only
pytest tests/api -q

# Requires maturin build
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release
pytest tests/integration/test_indexing.py -q
```

## Adding API tests

1. Add scenario to `api-contracts.md` first
2. Create `tests/api/test_<resource>.py`
3. Use `api_client` + `save_spaces_config` from `api/conftest.py`
4. Assert status code and JSON shape match contract examples

## Specs

- `openspec/changes/scout-simple-mvp1/specs/rest-api/spec.md`
- `api-contracts.md`
