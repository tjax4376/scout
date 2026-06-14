# Journal: UTF-8 chunk panic — stale pipx wheel

## Context

User hit `chunk.rs:87` panic during `scout scout reindex`:
`end byte index 3072 is not a char boundary; it is inside 'ὴ'`

## Discussion

- Fix already in source (`floor_char_boundary` in `scout_core/src/chunk.rs`) from 2026-06-12.
- pipx wheel at `dist/scout-0.1.0-*.whl` was built **before** fix — installed binary still panicked.
- Not a new bug; stale binary distribution.

## Code changed

None (fix pre-existing). Ops:
```bash
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin build --release --out dist
pipx uninstall scout && pipx install dist/scout-0.1.0-*.whl
maturin develop --release   # dev venv
```

## Test plan

- `cargo test -p scout_core split_oversized_respects_utf8`
- `scout scout reindex` completes past "Building graph and chunks"
