# Ops cards — Scout / Hawkeye

## Hawkeye: command not found

**Symptom:** `hawkeye: command not found` after clone.

**Fix:** Activate venv (`source .venv/bin/activate`) after `scripts/scout.sh build dev`, or use `scripts/hawkeye.sh`, `./.venv/bin/hawkeye`, or `pipx install dist/scout-*.whl`.

## Hawkeye setup 422 / space validation

**Symptom:** `hawkeye setup` fails probing Scout spaces.

**Fix:** Use `hawkeye setup --scout-api http://127.0.0.1:PORT/v1 --space NAME`. Discovery validates via `/spaces/list` only (no bare `/symbols` probe).

## OpenSpec CI validation fails (no changes/ in checkout)

**Symptom:** `no change directories found under openspec/changes/` or `no rest-api/spec.md found`.

**Cause:** `openspec/` was gitignored — only `config.yaml` tracked; specs and tests missing in CI.

**Fix:** Track `openspec/specs/` + `openspec/config.yaml`; keep `openspec/changes/` gitignored (local drafts). Validator uses canonical `openspec/specs/rest-api/spec.md` when no active changes. Run `python scripts/validate_openspec.py` before push.

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

## Scout API auth (security-hardening)

**Symptom:** `401 unauthorized` from Scout after upgrade.

**Fix:** Send `Authorization: Bearer $SCOUT_API_KEY`. Admin routes (`reindex`, `DELETE session/index`) need `SCOUT_ADMIN_KEY`. Localhost dev: `api.auth.enabled: false` in `config.yaml` or unset `SCOUT_AUTH_ENABLED`. Setup generates keys in `api.auth` block.

## Scout API auth (security-hardening)

**Symptom:** `401 unauthorized` from Scout after upgrade.

**Fix:** Send `Authorization: Bearer $SCOUT_API_KEY`. Admin routes (`reindex`, `DELETE session/index`) need `SCOUT_ADMIN_KEY`. Localhost dev: `api.auth.enabled: false` in `config.yaml` or unset `SCOUT_AUTH_ENABLED`. Setup generates keys in `api.auth` block.

## Scout API HTTPS redirect loop

**Symptom:** `301` redirect loop or clients cannot reach `/v1/health` after enabling HTTPS.

**Fix:** Terminate TLS at reverse proxy and forward `X-Forwarded-Proto: https`. For local dev keep loopback `http://127.0.0.1:PORT/v1` with `api.force_https: false`. LAN deploys: use `https://` in `api_base_url` or set `SCOUT_FORCE_HTTPS=1`.

## Scout API rate limit 429

**Symptom:** `429 rate limit exceeded` on search/reindex despite low traffic; or `test_search_rate_limit_returns_429` fails in full suite (`first.status_code != 429`).

**Cause:** Limits per IP **and** bearer token. Shared NAT users need distinct keys. In-memory limiter is process-global — earlier search tests consume the same bucket.

**Fix:** Tune `api.rate_limit.search_per_minute` / `reindex_per_hour` in config. API tests autouse `reset_rate_limiter()` via `tests/api/conftest.py`.

## Scout API path traversal 400

**Symptom:** `400` on `GET /v1/spaces/{space}/file?rel_path=...`

**Fix:** `rel_path` must be workspace-relative (no `..`, no absolute paths). URL-encoded traversal (`%2e%2e`) is rejected. Use paths like `src/main.py`.

## OpenSpec route validator vs APIRouter

**Symptom:** `validate_openspec.py` fails — routes in `app.py` not found after moving to `@v1_router`.

**Fix:** Use full `/v1/...` paths on `@v1_router` decorators; extend `APP_ROUTE_RE` to match `@v1_router` as well as `@app`.


**Symptom:** AI/subagent review cites files that don't exist in target repo (e.g. `api/controllers/user.js`, `business-rules.js`, `utils/validation.js`) or misattributes line ranges (e.g. `auth.js:120-150` described as nested RBAC but actual lines are UI form logic).

**Cause:** Hybrid escalation bundle sent to external AI; model invents generic e-commerce patterns not grounded in indexed/diff scope.

**Fix:** Verify every cited path exists before acting. Re-run with `hawkeye review --path <dir> --backend filesystem` and confirm file list. Prefer deterministic rule findings over hybrid advisory. If implementing fixes, confirm target repo path and open workspace to that project.
