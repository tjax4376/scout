#!/usr/bin/env bash
# Verify pipx install scout works from a built wheel (clean-machine simulation).
#
# Metadata: v0.1.0 | Scout Contributors | 2026-06-12
# Usage: scripts/verify_pipx_install.sh [wheel_path]
# Requires: pipx, python3.11+ (matches wheel ABI tag)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL="${1:-}"

if [[ -z "$WHEEL" ]]; then
  echo "Building wheel..."
  BUILD_PY="${PYTHON:-python3.12}"
  if ! command -v "$BUILD_PY" >/dev/null 2>&1; then
    BUILD_PY="python3"
  fi
  "$BUILD_PY" -m pip install -q maturin
  rm -rf "$ROOT/dist"
  "$BUILD_PY" -m maturin build --release --out "$ROOT/dist"
  WHEEL="$(ls "$ROOT"/dist/scout-*.whl | head -1)"
fi

if [[ ! -f "$WHEEL" ]]; then
  echo "Wheel not found: $WHEEL" >&2
  exit 1
fi

echo "Using wheel: $WHEEL"

PIPX_HOME="$(mktemp -d)"
PIPX_BIN_DIR="$(mktemp -d)"
export PIPX_HOME PIPX_BIN_DIR

INSTALL_PY="${PYTHON:-python3.12}"
if ! command -v "$INSTALL_PY" >/dev/null 2>&1; then
  INSTALL_PY="python3"
fi

echo "Installing with pipx (python: $INSTALL_PY)..."
pipx install --python "$INSTALL_PY" "$WHEEL"

echo "Checking scout CLI..."
"$PIPX_BIN_DIR/scout" >/dev/null

echo "Checking scout_core import..."
"$PIPX_HOME/venvs/scout/bin/python" -c \
  "import scout_core; print('scout_core', scout_core.py_core_version())"

echo "OK: pipx install verified"
