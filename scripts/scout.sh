#!/usr/bin/env bash
# Scout build & run helper.
#
# Metadata: v0.1.1 | Scout Contributors | 2026-06-14
# Rationale: one entrypoint for dev + production binary build and API start.
# Usage:
#   scripts/scout.sh build dev          # clean, build, activate .venv, start scout serve
#   scripts/scout.sh build production   # release wheel → .venv-prod
#   scripts/scout.sh start              # scout serve only (skip build)
#   scripts/scout.sh start production   # scout serve from production install
#   scripts/scout.sh validate           # OpenSpec structure + link checks

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PROD_VENV="$ROOT/.venv-prod"
DIST="$ROOT/dist"
PYTHON="${PYTHON:-python3}"

# Python 3.14+ needs abi3 forward compat at pyo3 build time.
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY="${PYO3_USE_ABI3_FORWARD_COMPATIBILITY:-1}"

usage() {
  cat >&2 <<EOF
Usage:
  $(basename "$0") build dev          # clean, build, start serve (foreground)
  $(basename "$0") build production
  $(basename "$0") start              # serve only (skip build)
  $(basename "$0") start production
  $(basename "$0") validate
EOF
  exit 1
}

activate_venv() {
  if [[ ! -d "$VENV" ]]; then
    echo "Creating venv at $VENV..."
    "$PYTHON" -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
}

activate_prod_venv() {
  if [[ ! -d "$PROD_VENV" ]]; then
    echo "Creating production venv at $PROD_VENV..."
    "$PYTHON" -m venv "$PROD_VENV"
  fi
  # shellcheck disable=SC1091
  source "$PROD_VENV/bin/activate"
}

install_python_deps() {
  pip install -q -U pip
  pip install -q maturin pytest pytest-asyncio httpx psutil pyyaml rich typer fastapi uvicorn pydantic
}

remove_stale_pid_files() {
  local pidfile
  for pidfile in "$ROOT/.scout/scout.pid" "$HOME/.scout/scout.pid"; do
    if [[ -f "$pidfile" ]]; then
      echo "Removing stale PID file: $pidfile"
      rm -f "$pidfile"
    fi
  done
}

stop_stale_serve() {
  if [[ -x "$VENV/bin/scout" ]]; then
    echo "Stopping scout serve (if running)..."
    "$VENV/bin/scout" stop-serve || true
    return
  fi
  remove_stale_pid_files
}

clean_stale_dev_artifacts() {
  echo "Removing stale build artifacts..."
  rm -rf "$DIST" "$ROOT/scout_core/target" "$ROOT/.pytest_cache"
  find "$ROOT/scout" "$ROOT/tests" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
}

clean_stale_venv_packages() {
  if [[ ! -x "$VENV/bin/pip" ]]; then
    return
  fi
  echo "Removing stale pip packages from .venv..."
  "$VENV/bin/pip" uninstall -y scout scout_core 2>/dev/null || true
}

clean_for_dev_build() {
  echo "=== Cleaning stale Scout dev state ==="
  stop_stale_serve
  clean_stale_dev_artifacts
  clean_stale_venv_packages
}

build_dev() {
  cd "$ROOT"
  clean_for_dev_build
  activate_venv
  install_python_deps
  echo "Building scout_core (maturin develop --release)..."
  maturin develop --release
  echo "Verifying scout_core..."
  python -c "import scout_core; print('scout_core', scout_core.py_core_version())"
  echo "OK: clean dev build verified"
  start_dev_serve
}

ensure_scout_core() {
  if ! python -c "import scout_core" 2>/dev/null; then
    echo "scout_core not built. Run: scripts/$(basename "$0") build dev" >&2
    exit 1
  fi
}

start_dev_serve() {
  cd "$ROOT"
  activate_venv
  ensure_scout_core
  echo "Starting scout serve (foreground — Ctrl+C to stop)..."
  echo "Other terminals: source $VENV/bin/activate"
  exec scout serve
}

build_production() {
  cd "$ROOT"
  activate_venv
  pip install -q -U pip maturin
  echo "Building production wheel..."
  rm -rf "$DIST"
  maturin build --release --out "$DIST"
  WHEEL="$(ls "$DIST"/scout-*.whl | head -1)"
  if [[ ! -f "$WHEEL" ]]; then
    echo "Wheel not found in $DIST" >&2
    exit 1
  fi
  echo "Installing wheel: $WHEEL"
  activate_prod_venv
  pip install -q -U pip
  pip install -q --force-reinstall "$WHEEL"
  echo "Verifying scout_core..."
  python -c "import scout_core; print('scout_core', scout_core.py_core_version())"
  echo "OK: production build ready — run: scripts/$(basename "$0") start production"
}

start() {
  start_dev_serve
}

start_production() {
  cd "$ROOT"
  activate_prod_venv
  if ! python -c "import scout_core" 2>/dev/null; then
    echo "Production scout not built. Run: scripts/$(basename "$0") build production" >&2
    exit 1
  fi
  exec scout serve
}

validate_openspec() {
  cd "$ROOT"
  echo "Validating OpenSpec structure and links..."
  exec "$PYTHON" scripts/validate_openspec.py
}

is_prod_target() {
  case "${1:-}" in
    production | prod) return 0 ;;
    *) return 1 ;;
  esac
}

case "${1:-}" in
  build)
    case "${2:-}" in
      dev) build_dev ;;
      production | prod) build_production ;;
      *) usage ;;
    esac
    ;;
  start)
    if is_prod_target "${2:-}"; then
      start_production
    elif [[ -z "${2:-}" ]]; then
      start
    else
      usage
    fi
    ;;
  validate) validate_openspec ;;
  *) usage ;;
esac
