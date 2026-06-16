# Ops cards — Scout / Hawkeye

## Hawkeye: command not found

**Symptom:** `hawkeye: command not found` after clone.

**Fix:** Activate venv (`source .venv/bin/activate`) after `scripts/scout.sh build dev`, or use `scripts/hawkeye.sh`, `./.venv/bin/hawkeye`, or `pipx install dist/scout-*.whl`.

## Hawkeye setup 422 / space validation

**Symptom:** `hawkeye setup` fails probing Scout spaces.

**Fix:** Use `hawkeye setup --scout-api http://127.0.0.1:PORT/v1 --space NAME`. Discovery validates via `/spaces/list` only (no bare `/symbols` probe).

## Hawkeye standalone binary

**Symptom:** Need Hawkeye without Python venv.

**Fix:** `scripts/scout.sh build hawkeye-binary` → `dist/hawkeye`. Filesystem review works offline: `dist/hawkeye review --backend filesystem --file path.py`. Graph mode still needs `scout serve`.

**macOS Gatekeeper:** `xattr -d com.apple.quarantine dist/hawkeye` if blocked.

**PyInstaller spec path:** `packaging/hawkeye.spec` uses `root = Path(SPECPATH).parent` (repo root), not `parent.parent`.

## Hawkeye filesystem backend

**Symptom:** Review without Scout / no `config.yaml`.

**Fix:** `hawkeye review --backend filesystem --path .` — skips `graph_neighbor` and `staleness_gate`; trace records `backend` + `skipped_rules`. Embedded pack via `load_config_or_defaults()`.

## Scout stale index

**Symptom:** `stale: true` in review.

**Fix:** `scout <space> reindex`.
