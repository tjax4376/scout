# Journal: Comprehensive README rewrite

**Date:** 2026-06-13 (updated)  
**Author:** Cursor agent  
**Version:** 0.1.0

## Context

User requested a full README covering all Scout features, CLI command structures, REST API calls, and end-to-end install from clone through build, setup, serve, and index. Follow-up: add Quick start, macOS install, Linux clone/build/compile, Windows fork-yourself note.

## Discussion points

- README must serve both new users (clone → first index) and agent integrators (REST + skills).
- Quick start at top for users who already have deps.
- Platform sections: macOS (Homebrew + LM Studio), Linux (apt + rustup + maturin compile), Windows explicitly unsupported — fork and DIY.
- Command shape `<space> <cmd>` is a common footgun — document explicitly.
- Two agent skills: `search_scout` (setup-installed) vs `code-reviewer-scout` (standalone `python -m scout.code_reviewer`).
- Embed batch defaults to auto-probe (`--embed-batch 0`); cache in `config.yaml`.
- pipx name collision with legacy PyPI `scout` 4.x documented with wheel install workaround.
- Full API detail stays in `api-contracts.md`; README summarizes with examples and links.

## Code / docs changed

| File | Change |
|------|--------|
| `README.md` | Full rewrite + platform install sections (macOS, Linux, Windows), quick start, after-install shared steps |

## Test plan

- [ ] New user can follow Quick start on macOS/Linux with deps installed
- [ ] macOS path: brew + xcode-select + scout.sh build dev
- [ ] Linux path: apt + rustup + maturin develop --release
- [ ] CLI examples match `scout/cli/main.py` usage strings
- [ ] API paths match `scout/api/app.py` and `api-contracts.md`
