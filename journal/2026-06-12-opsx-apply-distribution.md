# Journal: OpenSpec Apply — Distribution (16.2 + 16.3)

**Date:** 2026-06-12
**Author:** Cursor Agent
**Version:** 1.0

## Context

User ran `/opsx-apply` to finish MVP1 distribution tasks 16.2 (PyPI publish) and 16.3 (pipx clean-machine verify). Change: `scout-simple-mvp1`. 86/88 tasks were already complete.

## Discussion Points

- PyPI publish via `.github/workflows/publish.yml`: tag `v*` triggers multi-platform maturin wheel build (Linux x86_64+aarch64, macOS universal2, Windows) + sdist, upload to PyPI
- Trusted publishing (OIDC) + fallback `PYPI_API_TOKEN` secret
- Enabled `py-limited-api` (cp311-abi3) so one wheel per platform covers Python 3.11+
- `scout_core` native extension bundled inside `scout` wheel (not separate PyPI package)
- CI wheels job upgraded to ubuntu/macos/windows matrix via `PyO3/maturin-action`
- Verified locally: `scripts/verify_pipx_install.sh` — pipx install from abi3 wheel, `scout` CLI + `import scout_core` OK
- All 88/88 tasks now complete

## Code Changed

| Area | Files | Summary |
|------|-------|---------|
| Publish CI | `.github/workflows/publish.yml` | PyPI release on tag |
| CI wheels | `.github/workflows/ci.yml` | Multi-OS wheel matrix |
| Packaging | `pyproject.toml`, `scout_core/Cargo.toml` | abi3, PyPI classifiers/urls |
| Verify | `scripts/verify_pipx_install.sh` | pipx clean-machine simulation |
| Docs | `README.md`, `tasks.md` | Distribution instructions |
| Ignore | `.gitignore` | dist, .venv, .scout |

## Summary

MVP1 distribution wired. Maintainer tags `v0.1.0` → CI publishes to PyPI. Users install via `pipx install scout`. Archive change with `/opsx:archive scout-simple-mvp1`.
