#!/usr/bin/env bash
# Build standalone hawkeye binary via PyInstaller.
#
# Metadata: v1.4.0 | Scout Contributors | 2026-06-15
# Output: dist/hawkeye (or dist/hawkeye.exe on Windows)
#         $PREFIX/hawkeye          (if --prefix is given)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON="${PYTHON:-python3}"
PREFIX=""

# Parse --prefix argument
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      PREFIX="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

if [[ ! -d "$VENV" ]]; then
  echo "Creating venv at $VENV..."
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -q -U pip pyinstaller httpx pyyaml

if ! python -c "import scout.hawkeye" 2>/dev/null; then
  echo "Installing scout package for hawkeye entry..."
  pip install -q -e .
fi

rm -rf "$ROOT/build/hawkeye" "$ROOT/dist/hawkeye" "$ROOT/dist/hawkeye.exe"
pyinstaller packaging/hawkeye.spec --clean --noconfirm

BINARY="$ROOT/dist/hawkeye"
if [[ ! -x "$BINARY" ]] && [[ -f "$ROOT/dist/hawkeye.exe" ]]; then
  BINARY="$ROOT/dist/hawkeye.exe"
fi
if [[ ! -f "$BINARY" ]]; then
  echo "hawkeye binary not found in dist/" >&2
  exit 1
fi

"$BINARY" --help >/dev/null
echo "OK: hawkeye binary ready at $BINARY"

if [[ -n "$PREFIX" ]]; then
  INSTALL_DIR="$PREFIX"
  INSTALL_BIN="$INSTALL_DIR/hawkeye"
  mkdir -p "$INSTALL_DIR"
  cp "$BINARY" "$INSTALL_BIN"
  chmod +x "$INSTALL_BIN"
  "$INSTALL_BIN" --help >/dev/null
  echo "OK: hawkeye installed at $INSTALL_BIN"
fi
