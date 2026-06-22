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
# Isolation contract:
#   HOME        → isolated temp dir (so ~/.claude, ~/.codex, ~/.kiro, ~/.cursor all go there)
#   QIJU_HOME   → separate isolated temp dir (record store; never the real ~/.qiju)
# Neither touches real user files.
smoke_test() {
  log "Running local wheel smoke test (fully isolated HOME + QIJU_HOME)"
  VENV_DIR="$(mktemp -d /tmp/qiju-wheel-test-XXXXXX)"
  SMOKE_HOME="$(mktemp -d /tmp/qiju-smoke-home-XXXXXX)"
  QIJU_HOME_TEST="$(mktemp -d /tmp/qiju-smoke-qiju-XXXXXX)"
  ENTRY_FILE="$(mktemp)"

  cleanup() {
    rm -rf "$VENV_DIR" "$SMOKE_HOME" "$QIJU_HOME_TEST" "$ENTRY_FILE"
  }
  trap cleanup EXIT

  "$UV" venv "$VENV_DIR" --quiet
  QIJU_BIN="$VENV_DIR/bin/qiju"

  "$UV" pip install --quiet --python "$VENV_DIR/bin/python" "$WHEEL"

  # Fully isolate: HOME controls where --global writes (e.g. ~/.claude/skills, ~/.kiro/skills)
  export HOME="$SMOKE_HOME"
  export QIJU_HOME="$QIJU_HOME_TEST"

  log "  qiju --version"
  "$QIJU_BIN" --version

  # ── Host init ──────────────────────────────────────────────────────────────
  log "  qiju init --global for all four hosts (writes to isolated \$HOME)"
  for host in claude codex kiro cursor; do
    "$QIJU_BIN" init --host "$host" --global
    log "    init --host $host --global: OK"
  done

  # Verify each host's skill files landed in the isolated HOME
  for host in claude codex kiro cursor; do
    case "$host" in
      claude) skill_dir="$SMOKE_HOME/.claude/skills/qiju-log" ;;
      codex)  skill_dir="$SMOKE_HOME/.agents/skills/qiju-log" ;;
      kiro)   skill_dir="$SMOKE_HOME/.kiro/skills/qiju-log" ;;
      cursor) skill_dir="$SMOKE_HOME/.cursor/skills/qiju-log" ;;
    esac
    [ -d "$skill_dir" ] || die "init --host $host did not write to isolated HOME (expected: $skill_dir)"
  done
  log "  All four hosts wrote to isolated \$HOME — real user files untouched"

  # ── Log a record ───────────────────────────────────────────────────────────
  log "  qiju log round-trip"
  cat > "$ENTRY_FILE" <<'JSON'
{"title": "smoke test", "tags": ["smoke"], "search_terms": ["smoke"], "next_steps": [], "body_md": "wheel smoke test"}
JSON
  RECORD_ID="$("$QIJU_BIN" log --source manual --agent smoke --project smoke-test --body "$ENTRY_FILE" 2>/dev/null)"
  log "  logged: $RECORD_ID"

  log "  qiju search (pre-uninstall)"
  "$QIJU_BIN" search --scope all --query "smoke test" --limit 1 --format summary

  # ── Maintain ───────────────────────────────────────────────────────────────
  log "  qiju maintain --dry-run"
  "$QIJU_BIN" maintain --dry-run >/dev/null

  # ── Real uninstall (hosts only) — records must survive ─────────────────────
  log "  qiju uninstall --hosts all --user-only (real, not dry-run)"
  "$QIJU_BIN" uninstall --hosts all --user-only
  # Confirm host integration files removed from isolated HOME
  for host in claude codex kiro cursor; do
    case "$host" in
      claude) skill_dir="$SMOKE_HOME/.claude/skills/qiju-log" ;;
      codex)  skill_dir="$SMOKE_HOME/.agents/skills/qiju-log" ;;
      kiro)   skill_dir="$SMOKE_HOME/.kiro/skills/qiju-log" ;;
      cursor) skill_dir="$SMOKE_HOME/.cursor/skills/qiju-log" ;;
    esac
    [ ! -d "$skill_dir" ] || die "uninstall did not remove $host skill files: $skill_dir"
  done
  # Confirm records still exist
  [ -d "$QIJU_HOME_TEST/long" ] || die "uninstall deleted long/ records — must preserve"
  log "  Host files removed; long/ records preserved: OK"

  # ── Reinstall + record-persistence check ───────────────────────────────────
  log "  Reinstalling wheel into same venv"
  "$UV" pip install --quiet --python "$VENV_DIR/bin/python" --force-reinstall "$WHEEL"

  log "  qiju search (post-reinstall) — pre-existing record must still be searchable"
  SEARCH_OUT="$("$QIJU_BIN" search --scope all --query "smoke test" --limit 1 --format summary)"
  echo "$SEARCH_OUT" | grep -q "smoke test" || die "Pre-existing record not found after reinstall"
  log "  Record persistence after reinstall: OK"
  log "  $SEARCH_OUT"

  # ── Config loading from site-packages ──────────────────────────────────────
  log "  config/*.json loaded from site-packages (not source tree)"
  "$VENV_DIR/bin/python" -c "
from importlib.resources import files
cfg = files('qiju').joinpath('config/allowlist.json')
assert cfg.is_file(), f'allowlist.json not found at {cfg}'
print('  allowlist.json:', cfg)
assert 'site-packages' in str(cfg), f'Expected site-packages path, got: {cfg}'
"

  log "Smoke test PASSED — all checks green, real user files untouched"
}

case "$MODE" in
  --smoke)
    smoke_test
    ;;
  --test-pypi)
    [ -n "${TESTPYPI_TOKEN:-}" ] || die "TESTPYPI_TOKEN env var not set"
    log "Uploading to TestPyPI"
    # Token via env var only — never --token on CLI (D12: token must not appear in process args)
    # Pass explicit globs — never dist/* which would include SHA256SUMS
    UV_PUBLISH_TOKEN="$TESTPYPI_TOKEN" "$UV" publish \
      --publish-url https://test.pypi.org/legacy/ \
      "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz
    log "Uploaded. Install from TestPyPI with dual-index (qiju from TestPyPI, duckdb from prod):"
    log "  uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ qiju==$VERSION"
    smoke_test
    ;;
  --prod-pypi)
    [ -n "${PYPI_TOKEN:-}" ] || die "PYPI_TOKEN env var not set"
    # Verify name is still free immediately before upload
    if curl -sf "https://pypi.org/pypi/qiju/json" >/dev/null 2>&1; then
      die "qiju already exists on PyPI — check before uploading"
    fi
    log "Uploading to production PyPI"
    # Token via env var only — never --token on CLI (D12)
    UV_PUBLISH_TOKEN="$PYPI_TOKEN" "$UV" publish \
      "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz
    log "Published qiju $VERSION to PyPI"
    ;;
  *)
    die "Unknown mode: $MODE (use --smoke, --test-pypi, or --prod-pypi)"
    ;;
esac
