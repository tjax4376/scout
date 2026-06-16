#!/usr/bin/env bash
# Verify pipx install scout works from a built wheel (clean-machine simulation).
#
# Metadata: v0.1.1 | Scout Contributors | 2026-06-15
# Usage: scripts/verify_pipx_install.sh [wheel_path]
# Requires: pipx, python3.11+ (matches wheel ABI tag)
# Checks: scout CLI, hawkeye CLI, scout_core import, hawkeye rule pack

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL="${1:-}"

if [[ -z "$WHEEL" ]]; then
  echo "Building wheel..."
  BUILD_PY="${PYTHON:-python3.12}"
  if ! command -v "$BUILD_PY" >/dev/null 2>&1; then
    BUILD_PY="python3"
  fi
  export PYO3_USE_ABI3_FORWARD_COMPATIBILITY="${PYO3_USE_ABI3_FORWARD_COMPATIBILITY:-1}"
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

VENV_PY="$PIPX_HOME/venvs/scout/bin/python"

echo "Checking scout CLI..."
"$PIPX_BIN_DIR/scout" --help >/dev/null

echo "Checking hawkeye CLI..."
"$PIPX_BIN_DIR/hawkeye" --help >/dev/null

echo "Checking scout_core import..."
"$VENV_PY" -c \
  "import scout_core; print('scout_core', scout_core.py_core_version())"

echo "Checking hawkeye rule pack..."
"$VENV_PY" -c "
from scout.hawkeye.config import _read_pack_yaml
pack = _read_pack_yaml('rules.yaml')
rules = pack.get('rules') or []
assert rules, 'hawkeye rules pack empty'
print('hawkeye pack OK', len(rules), 'rules')
"

echo "OK: pipx install verified (scout + hawkeye)"
