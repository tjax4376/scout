# GET /v1/spaces/list

**Context:** User requested endpoint to list available spaces served by `scout serve`.

## Discussion points

1. Route: `GET /v1/spaces/list` (static path before `{space}` routes)
2. Data source: `load_config(home).spaces` — same config as other space routes
3. Response: name, root, skip_globs, skip_paths per space; sorted by name
4. No embed/core dependency — config-only like health

## Summary

Added list endpoint for agent discovery. Updated `api-contracts.md` and `skills/search_scout/SKILL.md`. Two pytest cases in `tests/test_api.py`.

## Code changed

| File | Change |
|------|--------|
| `scout/api/app.py` | `SpaceInfo`, `SpaceListResponse`, `GET /v1/spaces/list` |
| `tests/test_api.py` | New — empty + sorted list tests |
| `api-contracts.md` | Document list endpoint |
| `skills/search_scout/SKILL.md` | Add endpoint to table |
