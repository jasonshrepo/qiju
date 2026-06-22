#!/usr/bin/env bash
# Verify wheel and sdist contents against expected file lists.
# Usage: bash verify_artifact.sh <dist_dir> <version>
set -euo pipefail

DIST_DIR="${1:?Usage: verify_artifact.sh <dist_dir> <version>}"
VERSION="${2:?Usage: verify_artifact.sh <dist_dir> <version>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "  [verify] $*"; }

WHEEL="$DIST_DIR/qiju-${VERSION}-py3-none-any.whl"
SDIST="$DIST_DIR/qiju-${VERSION}.tar.gz"

[ -f "$WHEEL" ] || die "Wheel not found: $WHEEL"
[ -f "$SDIST" ] || die "Sdist not found: $SDIST"

log "Wheel: $(basename "$WHEEL")"
log "Sdist: $(basename "$SDIST")"

# ── Wheel contents ────────────────────────────────────────────────────────────
WHEEL_FILES="$(python3 -c "
import zipfile, sys
with zipfile.ZipFile('$WHEEL') as z:
    names = sorted(n for n in z.namelist() if not n.endswith('/'))
    print('\n'.join(names))
")"

EXPECTED_WHEEL="$SCRIPT_DIR/expected-wheel-files.txt"
# Fail if the expected list is missing — it must be reviewed and committed, not auto-generated.
[ -f "$EXPECTED_WHEEL" ] || die "expected-wheel-files.txt is missing. Generate with: bash packaging/pypi/generate_expected.sh $DIST_DIR $VERSION"
EXPECTED="$(grep -v '^#' "$EXPECTED_WHEEL" | grep -v '^$' | sort)"
if [ "$WHEEL_FILES" != "$EXPECTED" ]; then
  echo "Wheel file list MISMATCH" >&2
  echo "=== Got ===" >&2
  echo "$WHEEL_FILES" >&2
  echo "=== Expected ===" >&2
  echo "$EXPECTED" >&2
  die "Wheel content check failed — if intentional, update expected-wheel-files.txt and commit"
fi
log "Wheel file list matches expected-wheel-files.txt"

# ── Sdist contents ────────────────────────────────────────────────────────────
SDIST_FILES="$(tar tzf "$SDIST" | grep -v '/$' | sort)"

EXPECTED_SDIST="$SCRIPT_DIR/expected-sdist-files.txt"
[ -f "$EXPECTED_SDIST" ] || die "expected-sdist-files.txt is missing. Generate with: bash packaging/pypi/generate_expected.sh $DIST_DIR $VERSION"
EXPECTED="$(grep -v '^#' "$EXPECTED_SDIST" | grep -v '^$' | sort)"
if [ "$SDIST_FILES" != "$EXPECTED" ]; then
  echo "Sdist file list MISMATCH" >&2
  echo "=== Got ===" >&2
  echo "$SDIST_FILES" >&2
  echo "=== Expected ===" >&2
  echo "$EXPECTED" >&2
  die "Sdist content check failed — if intentional, update expected-sdist-files.txt and commit"
fi
log "Sdist file list matches expected-sdist-files.txt"

# ── twine check ───────────────────────────────────────────────────────────────
# IMPORTANT: pass explicit globs for whl and tar.gz — never dist/* which would
# include SHA256SUMS and cause twine to error on an unknown distribution format.
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
if "$UV" tool list 2>/dev/null | grep -q twine || command -v twine >/dev/null 2>&1; then
  log "Running twine check"
  twine check "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz || die "twine check failed"
else
  log "twine not installed — skipping metadata check (install with: uv tool install twine)"
fi

log "Artifact verification passed"
