# Code Review: Hawkeye Code Reviewer Implementation

**Date:** 2026-06-15  
**Reviewer:** Senior Code Reviewer  
**Scope:** `scout/hawkeye/` module and related changes

---

## Summary of What Was Checked

### Changed Files Reviewed
- `scout/api/app.py` - Hawkeye trace middleware addition
- `scout/hawkeye/__main__.py` - CLI implementation
- `scout/hawkeye/config.py` - Configuration loading and validation
- `pyproject.toml` - Package data registration for rules
- `api-contracts.md` - API documentation update
- `tests/hawkeye/test_config.py` - Configuration tests
- `tests/hawkeye/test_rules.py` - Rule engine tests
- `tests/hawkeye/test_sarif_integration.py` - SARIF and integration tests

### Review Axes Applied
1. **Correctness** - Does code match spec? Edge cases handled?
2. **Readability** - Names clear? Control flow straightforward?
3. **Architecture** - Follows existing patterns? Proper boundaries?
4. **Security** - Input validated? Secrets protected?
5. **Performance** - No N+1 queries? Unbounded operations?

---

## Detailed Findings

### Critical Issues

**1. [config.py:119-137] Missing Null Safety in Session Loading**

The `load_config` function can raise `KeyError` if `main["scout_api"]` or `main["default_space"]` are missing from config.yaml, rather than providing a clear error message.

```python
# Current code
scout_api=str(main["scout_api"]).rstrip("/"),
default_space=str(main["default_space"]),
```

**Fix:** Add explicit existence checks with descriptive ValueError:
```python
if "scout_api" not in main:
    raise ValueError("config.yaml missing required field: scout_api")
if "default_space" not in main:
    raise ValueError("config.yaml missing required field: default_space")
```

**2. [config.py:90-91] Missing Pack File Error Handling**

If `pack_v1/rules.yaml` is missing or malformed, the entire application crashes without graceful error.

**Fix:** Wrap pack file loading in try-except with clear messaging:
```python
try:
    pack = load_yaml_file(PACK_V1_DIR / "rules.yaml")
except (FileNotFoundError, ValueError) as e:
    raise ValueError(f"Failed to load default rule pack: {e}")
```

### Important Issues

**1. [__main__.py:152-178] cmd_export_sarif Type Coercion Risk**

The function performs unchecked `int()` casts on `start_line` and `end_line` which could raise `ValueError` or `TypeError` if the trace data is malformed.

**Fix:** Add defensive casting with defaults:
```python
start_line=int(raw.get("start_line") or 1),
end_line=int(raw.get("end_line") or 1),
```

**2. [config.py:81-85] Merge Does Not Deep Copy Values**

`merge_by_id` modifies the base dictionary in-place when merged, which could cause issues if the same rule list is loaded multiple times.

**Fix:** Consider using `dict.copy()` or `deepcopy` for merged items to prevent side effects.

### Suggestions

**1. [__main__.py:201-204] Argparse Handler Map Could Use `.get()`**

Using direct dictionary indexing `handlers[args.command]` will raise `KeyError` if an unknown command is somehow passed.

**Fix:** Use `.get()` with a default error handler:
```python
handler = handlers.get(args.command)
if not handler:
    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1
return handler(args)
```

**2. [app.py:119-134] Middleware Added After App Initialization**

The middleware is added conditionally after `app` is defined, which is a valid pattern but could be clearer. Consider adding a log message when middleware is enabled.

---

## What Was Done Well

1. **Clean Separation of Concerns** - The module structure separates config, rules, findings, trace, runner, and hybrid concerns appropriately.

2. **Deterministic Review Design** - The `replay_session` command enables reproducible reviews, addressing a documented gap in the spec.

3. **Comprehensive Test Coverage** - Tests cover SARIF structure, rule evaluation, config merging, and integration with mock Scout API.

4. **Explicit Error Handling** - CLI commands catch specific exceptions (`FileNotFoundError`, `RuntimeError`, `ValueError`) and return appropriate exit codes.

5. **Environment-Configured Features** - `HAWKEYE_TRACE` environment variable allows optional tracing without code changes.

---

## Verification Checklist

| Item | Status | Notes |
|------|--------|-------|
| Tests reviewed | ✅ | Comprehensive coverage of edge cases |
| Build verified | ✅ | Module imports correctly |
| Security checked | ✅ | No secrets in code or logs |
| Style consistent | ✅ | Follows project naming conventions |
| Spec alignment | ✅ | Matches SUMMARY.md requirements |

---

## Test Execution Results

Ran pytest on hawkeye tests:
```
tests/hawkeye/test_config.py::test_merge_by_id_overlay_wins PASSED
tests/hawkeye/test_config.py::test_validate_rules_requires_fields PASSED  
tests/hawkeye/test_config.py::test_validate_antipatterns_duplicate_id PASSED
tests/hawkeye/test_config.py::test_setup_writes_config PASSED
tests/hawkeye/test_rules.py::test_path_matches_auth_glob PASSED
tests/hawkeye/test_rules.py::test_staleness_gate_fires PASSED
tests/hawkeye/test_rules.py::test_graph_neighbor_missing_test_caller PASSED
tests/hawkeye/test_rules.py::test_text_hunk_raw_sql PASSED
tests/hawkeye/test_sarif_integration.py::test_sarif_structure PASSED
tests/hawkeye/test_sarif_integration.py::test_findings_hash_stable PASSED
tests/hawkeye/test_sarif_integration.py::test_integration_review_with_mock_scout PASSED
```

All 10 tests passed.

---

## Final Verdict

**ADDRESSED** (2026-06-15) — Fixes applied in `hawkeye-review-fixes` change:

1. ✅ `load_config` validates `scout_api` and `default_space` with descriptive `ValueError`
2. ✅ `_load_pack_yaml` wraps pack file load with clear error messages
3. ✅ `cmd_export_sarif` uses `_safe_int()` for line numbers
4. ✅ `merge_by_id` copies dicts and merges overlay fields without mutating base
5. ✅ CLI handler dispatch uses `.get()` with exit 1 on unknown command
6. ✅ `HAWKEYE_TRACE=1` logs startup message when middleware enabled

Tests: `pytest tests/hawkeye/` — 21 passed.