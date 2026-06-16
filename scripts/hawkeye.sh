#!/usr/bin/env bash
# Run hawkeye from the project dev venv (no manual activate required).
#
# Usage: scripts/hawkeye.sh [--help | setup | review | ...]
# Metadata: v0.1.0 | Scout Contributors | 2026-06-15

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON="${PYTHON:-python3}"

if [[ -x "$VENV/bin/hawkeye" ]]; then
  exec "$VENV/bin/hawkeye" "$@"
fi

if command -v hawkeye >/dev/null 2>&1; then
  exec hawkeye "$@"
fi

if [[ -x "$VENV/bin/python" ]] && "$VENV/bin/python" -c "import scout.hawkeye" 2>/dev/null; then
  exec "$VENV/bin/python" -m scout.hawkeye "$@"
fi

cat >&2 <<EOF
hawkeye not found.

From repo root:
  scripts/scout.sh build dev    # build + install scout + hawkeye into .venv
  source .venv/bin/activate
  hawkeye --help

Or without activate:
  scripts/hawkeye.sh --help
  ./.venv/bin/hawkeye --help
  python -m scout.hawkeye --help
EOF
exit 1
