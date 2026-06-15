# code-reviewer-scout skill (maintainer docs)

Agent skill for **graph-first code review**: symbols first, map connections, read targeted file ranges, optional session search.

## Workflow

1. **Scope** — `path_prefix` from PR/diff
2. **Symbols (required)** — `GET /symbols` or `review_api.py map` — **before any file read**
3. **Connections (optional)** — `GET /neighbors`
4. **Read (targeted)** — `GET /file` using symbol line numbers (authoritative source)
5. **Search (optional)** — `POST /search` when `scout serve --embed`; read files first
6. **Audit** — use `compressed_text` or `/file` text; trace connections as needed

**Hard rule:** no IDE Read / `GET /file` until symbols listed for that path prefix.

## Session embed

- `scout serve --embed` + embed config
- Each `GET /file` enqueues background embed (deduped)
- Search hits: `snippet` + `compressed_text` + `session_scoped: true`
- Full source always via `GET /file`

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Agent-facing review workflow (injected at install) |
| `scripts/review_api.py` | Helper: map, symbols, neighbors, node, file, search |

## Install

Run from **repository root**:

```bash
python -m scout.code_reviewer \
  --agent cursor \
  --project \
  --project-root . \
  --scout-api http://127.0.0.1:8741/v1 \
  --default-space myapp \
  --force
```

## Helper commands

```bash
python skills/code-reviewer-scout/scripts/review_api.py map myapp scout/embed/
python skills/code-reviewer-scout/scripts/review_api.py neighbors myapp NODE_ID
python skills/code-reviewer-scout/scripts/review_api.py file myapp scout/api/app.py --start-line 80 --end-line 150
python skills/code-reviewer-scout/scripts/review_api.py search myapp "auth validation" --path-prefix scout/api/
```

## Contract reference

[`api-contracts.md`](../../api-contracts.md) — search (`compressed_text`), node, symbols, file, session status

## Specs

- `openspec/changes/session-embed-on-read/`
- `openspec/changes/embed-chunk-compression/`
- `openspec/changes/reviewer-symbols-first/`
