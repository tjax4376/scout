# scout.code_reviewer

Standalone install module for the `code-reviewer-scout` agent skill. Does **not** modify `scout/skill/` or the setup wizard.

## Purpose

Installs skill that instructs AI code reviewers to load context from Scout's in-memory index (via REST) instead of reading full files into session — reducing review token cost.

## Usage

```bash
python -m scout.code_reviewer \
  --agent cursor \
  --project \
  --project-root . \
  --scout-api http://127.0.0.1:8741/v1 \
  --default-space myapp
```

| Flag | Description |
|------|-------------|
| `--agent` | `cursor`, `pi`, or `opencode` |
| `--global` | Install to user home agent skills path |
| `--project` | Install to project agent skills path |
| `--project-root` | Project root (default: cwd) |
| `--scout-api` | API base URL with `/v1` suffix |
| `--default-space` | Scout space name |
| `--force` | Overwrite existing install |

## Install paths (hyphens only)

| Agent | Global | Project |
|-------|--------|---------|
| Cursor | `~/.cursor/skills/code-reviewer-scout/` | `<root>/.cursor/skills/code-reviewer-scout/` |
| Pi | `~/.pi/skills/code-reviewer-scout/` | `<root>/.pi/skills/code-reviewer-scout/` |
| OpenCode | `~/.config/opencode/skills/code-reviewer-scout/` | `<root>/.opencode/skills/code-reviewer-scout/` |

## Module layout

- `install.py` — `install_code_reviewer_skill()`, `AGENT_PATHS`, template injection
- `__main__.py` — CLI entry point

## Tests

`tests/code_reviewer/`

## Spec

`openspec/changes/ai-code-reviewer-scout/specs/code-reviewer-skill/spec.md`
