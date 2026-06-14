# Journal: chunk.rs UTF-8 boundary panic fix

**Date:** 2026-06-12  
**Author:** Cursor agent  
**Version:** scout_core chunk.rs  
**Change rationale:** Prevent index crash when oversized symbols contain multi-byte UTF-8

## Context

User hit panic during workspace scan/index:

```
thread panicked at scout_core/src/chunk.rs:87:26:
end byte index 3072 is not a char boundary; it is inside 'ὴ' (bytes 3071..3074)
```

Source was Python with Greek Unicode string literals in a large function body. `split_oversized` used byte offsets from a 4-chars-per-token heuristic without aligning to UTF-8 char boundaries.

## Discussion points

- Tree-sitter `start_byte`/`end_byte` are valid boundaries; bug only in manual split loop
- Fix: floor slice indices to char boundaries; ensure at least one char per chunk when target lands mid-char
- Overlap step also floors `start` to avoid mid-char resume
- No architecture change; localized fix in `chunk.rs`

## Code changed

| File | Change |
|------|--------|
| `scout_core/src/chunk.rs` | `floor_char_boundary()` helper; safe slicing in `split_oversized` and `extract_text`; 2 unit tests |
| `.memory/cards.md` | Issue + resolution card |

## Test plan

- [x] `cargo test chunk::` — UTF-8 Greek repeat source splits without panic
- [x] `extract_text_floors_to_char_boundary` — partial byte end truncates before multi-byte char
- [ ] Re-run user's workspace scan to confirm end-to-end index completes

## Security / PHA

Low risk — string indexing only; no new external input surface.
