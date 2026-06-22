#!/usr/bin/env bash
# Build the qiju PyPI wheel and sdist from release/src/qiju/ into pypi-build/dist/
# Usage: bash development/packaging/pypi/build.sh [--skip-scan]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RELEASE_DIR="$REPO_ROOT/release"
BUILD_DIR="$REPO_ROOT/pypi-build"
STAGING_DIR="$BUILD_DIR/staging"
DIST_DIR="$BUILD_DIR/dist"
SKIP_SCAN=0

for arg in "$@"; do
  case "$arg" in
    --skip-scan) SKIP_SCAN=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

# ── Step 1: Read and cross-check version ──────────────────────────────────────
PYPROJECT="$RELEASE_DIR/pyproject.toml"
[ -f "$PYPROJECT" ] || die "release/pyproject.toml not found — sync release first"

VERSION="$(grep -m1 '^version' "$PYPROJECT" | cut -d'"' -f2)"
[ -n "$VERSION" ] || die "could not read version from pyproject.toml"

CHANGELOG="$RELEASE_DIR/CHANGELOG.md"
if [ -f "$CHANGELOG" ]; then
  # Skip [Unreleased] and find the first actual version heading
  TOP_VERSION="$(grep '^## \[' "$CHANGELOG" | grep -v '^\## \[Unreleased\]' | head -1 | sed 's/^## \[\([^]]*\)\].*/\1/')"
  if [ "$TOP_VERSION" != "$VERSION" ]; then
    die "Version mismatch: pyproject.toml=$VERSION but CHANGELOG top version heading=[$TOP_VERSION]. Update CHANGELOG first."
  fi
fi

log "Building qiju $VERSION"

# ── Step 2: Clean staging and dist ───────────────────────────────────────────
log "Cleaning pypi-build/staging and pypi-build/dist"
rm -rf "$STAGING_DIR" "$DIST_DIR"
mkdir -p "$STAGING_DIR/src" "$DIST_DIR"

# ── Step 3: Copy source files ─────────────────────────────────────────────────
log "Copying release/src/qiju → staging/src/qiju"
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
  "$RELEASE_DIR/src/qiju/" "$STAGING_DIR/src/qiju/"

for f in pyproject.toml LICENSE NOTICE README.md; do
  [ -f "$RELEASE_DIR/$f" ] || die "Missing $f in release/"
  cp "$RELEASE_DIR/$f" "$STAGING_DIR/$f"
done

# ── Step 4: Completeness check (copy-too-little guard) ────────────────────────
log "Completeness check: staged vs. source package files"
SOURCE_FILES="$(find "$RELEASE_DIR/src/qiju" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' | sed "s|$RELEASE_DIR/src/qiju/||" | sort)"
STAGED_FILES="$(find "$STAGING_DIR/src/qiju" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '*.pyo' | sed "s|$STAGING_DIR/src/qiju/||" | sort)"

if [ "$SOURCE_FILES" != "$STAGED_FILES" ]; then
  echo "Source files:" >&2
  echo "$SOURCE_FILES" >&2
  echo "Staged files:" >&2
  echo "$STAGED_FILES" >&2
  die "Completeness check failed: staged file set differs from source package"
fi
log "Completeness check passed ($(echo "$SOURCE_FILES" | wc -l | tr -d ' ') files)"

# ── Step 5: Security scan ─────────────────────────────────────────────────────
if [ "$SKIP_SCAN" -eq 0 ]; then
  log "Running three-category security scan"
  python "$SCRIPT_DIR/scan.py" "$STAGING_DIR" || die "Security scan failed — see above"
else
  log "Skipping security scan (--skip-scan)"
fi

# ── Step 6: Build wheel and sdist ─────────────────────────────────────────────
log "Building wheel and sdist"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
(cd "$STAGING_DIR" && "$UV" build --out-dir "$DIST_DIR")

# ── Step 7: Verify artifacts ──────────────────────────────────────────────────
log "Verifying artifacts"
bash "$SCRIPT_DIR/verify_artifact.sh" "$DIST_DIR" "$VERSION"

# ── Step 8: SHA256SUMS ───────────────────────────────────────────────────────
log "Writing SHA256SUMS"
(cd "$DIST_DIR" && shasum -a 256 ./* > SHA256SUMS)
cat "$DIST_DIR/SHA256SUMS"

log "Build complete → $DIST_DIR"
log "Artifacts:"
ls -lh "$DIST_DIR"
