#!/usr/bin/env bash
# Publish qiju to TestPyPI (step A: local smoke) or production PyPI.
# Usage:
#   bash development/packaging/pypi/publish.sh --smoke          # local wheel smoke test only
#   bash development/packaging/pypi/publish.sh --test-pypi      # upload to TestPyPI, then smoke
#   bash development/packaging/pypi/publish.sh --prod-pypi      # upload to production PyPI
#
# Tokens must be set in environment — never passed on command line:
#   TESTPYPI_TOKEN   — for --test-pypi
#   PYPI_TOKEN       — for --prod-pypi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BUILD_DIR="$REPO_ROOT/pypi-build"
DIST_DIR="$BUILD_DIR/dist"
RELEASE_DIR="$REPO_ROOT/release"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

MODE="${1:-}"
[ -n "$MODE" ] || { echo "Usage: $0 --smoke|--test-pypi|--prod-pypi" >&2; exit 1; }

VERSION="$(grep -m1 '^version' "$RELEASE_DIR/pyproject.toml" | cut -d'"' -f2)"
WHEEL="$DIST_DIR/qiju-${VERSION}-py3-none-any.whl"
[ -f "$WHEEL" ] || die "Wheel not found: $WHEEL — run build.sh first"

# ── Step A: Local installed-wheel smoke test ──────────────────────────────────
smoke_test() {
  log "Running local wheel smoke test"
  VENV_DIR="/tmp/qiju-wheel-test-$$"
  QIJU_HOME_TEST="$(mktemp -d)"
  trap 'rm -rf "$VENV_DIR" "$QIJU_HOME_TEST"' EXIT

  "$UV" venv "$VENV_DIR" --quiet
  QIJU_BIN="$VENV_DIR/bin/qiju"

  "$UV" pip install --quiet --python "$VENV_DIR/bin/python" "$WHEEL"

  export QIJU_HOME="$QIJU_HOME_TEST"

  log "  qiju --version"
  "$QIJU_BIN" --version

  log "  qiju init for all four hosts"
  for host in claude codex kiro cursor; do
    "$QIJU_BIN" init --host "$host" --global
    log "    init --host $host --global: OK"
  done

  log "  qiju log round-trip"
  ENTRY_FILE="$(mktemp)"
  cat > "$ENTRY_FILE" <<'JSON'
{"title": "smoke test", "tags": ["smoke"], "search_terms": ["smoke"], "next_steps": [], "body_md": "wheel smoke test"}
JSON
  RECORD_ID="$("$QIJU_BIN" log --source manual --agent smoke --project smoke-test --body "$ENTRY_FILE" 2>/dev/null)"
  log "  logged: $RECORD_ID"

  log "  qiju search"
  "$QIJU_BIN" search --scope all --query "smoke test" --limit 1 --format summary

  log "  qiju maintain"
  "$QIJU_BIN" maintain --dry-run

  log "  qiju uninstall --hosts all (records survive)"
  "$QIJU_BIN" uninstall --hosts all --user-only --dry-run

  log "  config/*.json loaded from site-packages (not source tree)"
  "$VENV_DIR/bin/python" -c "
from importlib.resources import files
cfg = files('qiju').joinpath('config/allowlist.json')
assert cfg.is_file(), f'allowlist.json not found at {cfg}'
print('  allowlist.json:', cfg)
"

  log "Smoke test PASSED"
}

case "$MODE" in
  --smoke)
    smoke_test
    ;;
  --test-pypi)
    [ -n "${TESTPYPI_TOKEN:-}" ] || die "TESTPYPI_TOKEN env var not set"
    log "Uploading to TestPyPI"
    UV_PUBLISH_TOKEN="$TESTPYPI_TOKEN" "$UV" publish \
      --publish-url https://test.pypi.org/legacy/ \
      "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz
    log "Uploaded. Install from TestPyPI with:"
    log "  uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ qiju==$VERSION"
    smoke_test
    ;;
  --prod-pypi)
    [ -n "${PYPI_TOKEN:-}" ] || die "PYPI_TOKEN env var not set"
    # Verify name is still free
    if curl -sf "https://pypi.org/pypi/qiju/json" >/dev/null 2>&1; then
      die "qiju already exists on PyPI — check before uploading"
    fi
    log "Uploading to production PyPI"
    UV_PUBLISH_TOKEN="$PYPI_TOKEN" "$UV" publish \
      "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz
    log "Published qiju $VERSION to PyPI"
    ;;
  *)
    die "Unknown mode: $MODE (use --smoke, --test-pypi, or --prod-pypi)"
    ;;
esac
