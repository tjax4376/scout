# code-reviewer-scout skill (maintainer docs)

Agent skill for token-efficient code review. Instructs reviewers to load context from Scout's in-memory index via REST instead of reading full files into session.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Agent-facing review workflow (injected at install) |
| `scripts/review_api.py` | Terminal helper for path-scoped search and node lookup |

## Install

Standalone — not part of `scout setup`:

```bash
python -m scout.code_reviewer \
  --agent cursor \
  --project \
  --project-root /path/to/repo \
  --scout-api http://127.0.0.1:8741/v1 \
  --default-space myapp
```

Add `--global` for user-level install. Use `--force` to overwrite existing copy.

## Agent paths (hyphens only)

| Agent | Global | Project |
|-------|--------|---------|
| Cursor | `~/.cursor/skills/code-reviewer-scout/` | `<root>/.cursor/skills/code-reviewer-scout/` |
| Pi | `~/.pi/skills/code-reviewer-scout/` | `<root>/.pi/skills/code-reviewer-scout/` |
| OpenCode | `~/.config/opencode/skills/code-reviewer-scout/` | `<root>/.opencode/skills/code-reviewer-scout/` |

Frontmatter `name: code-reviewer-scout` — all agents require hyphens, no underscores.

## Contract reference

Full API shapes: [`api-contracts.md`](../../api-contracts.md)

## Tests

`tests/code_reviewer/`

## Specs

`openspec/changes/ai-code-reviewer-scout/specs/code-reviewer-skill/spec.md`
