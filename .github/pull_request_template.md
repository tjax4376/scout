## Summary

<!-- What changed and why (1–3 sentences) -->

## Type

- [ ] Feature
- [ ] Bug fix
- [ ] Refactor / docs
- [ ] CI / tooling

## Checklist

### Tests
- [ ] `pytest -q` passes locally
- [ ] `cargo test -p scout_core` passes (if Rust touched)
- [ ] New/changed API routes have tests in `tests/api/` matching `api-contracts.md`

### API contract
- [ ] If REST routes changed: updated `api-contracts.md`
- [ ] If agent skill behavior changed: updated `skills/search_scout/SKILL.md`

### OpenSpec
- [ ] Related change spec exists under `openspec/changes/`
- [ ] Tasks marked complete in `tasks.md` for implemented items
- [ ] Cross-references added/updated in related spec files
- [ ] `python scripts/validate_openspec.py` passes (structure, links, api-contracts ↔ spec ↔ app.py)

### Build
- [ ] `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release` succeeds (if scout_core touched)
- [ ] No secrets or `.env` files committed

## Test plan

<!-- Steps reviewer can follow to verify -->
