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

# ── Step 6: Build wheel and sdist (deterministic via SOURCE_DATE_EPOCH) ───────
log "Building wheel and sdist"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
# Pin archive entry timestamps to the last release/ commit so successive builds
# from the same source produce identical bytes (D14).
SOURCE_DATE_EPOCH="$(git -C "$RELEASE_DIR" log -1 --format=%ct)"
export SOURCE_DATE_EPOCH
log "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH (last release/ commit)"
(cd "$STAGING_DIR" && "$UV" build --out-dir "$DIST_DIR")

# Normalize the sdist for deterministic bytes (D14):
# - SOURCE_DATE_EPOCH covers source-file tar entry timestamps, but setuptools-
#   generated files (setup.cfg, PKG-INFO, egg-info) still get wall-clock mtimes.
# - The gzip wrapper header also records the current compression time.
# Fix: re-pack the tar with all entry mtimes pinned to SOURCE_DATE_EPOCH,
# then recompress with a fixed gzip header mtime.
SDIST="$DIST_DIR/qiju-${VERSION}.tar.gz"
python3 - "$SDIST" <<PYEOF
import gzip, io, os, sys, tarfile
path = sys.argv[1]
epoch = int(os.environ["SOURCE_DATE_EPOCH"])
# Decompress
with open(path, "rb") as f:
    raw_tar = gzip.decompress(f.read())
# Repack tar: normalize all entry mtimes, uid/gid, sort by name
tar_buf = io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as src:
    members = sorted(src.getmembers(), key=lambda m: m.name)
    with tarfile.open(fileobj=tar_buf, mode="w:", format=tarfile.PAX_FORMAT) as dst:
        for m in members:
            m.mtime = epoch
            m.uid = 0
            m.gid = 0
            m.uname = ""
            m.gname = ""
            # PAX format uses pax_headers["mtime"] over m.mtime — clear it
            # so our integer epoch is what gets written.
            m.pax_headers = {}
            fobj = src.extractfile(m) if m.isfile() else None
            dst.addfile(m, fobj)
# Recompress with fixed gzip header mtime
buf = io.BytesIO()
with gzip.GzipFile(filename="", mode="wb", mtime=epoch, fileobj=buf) as gz:
    gz.write(tar_buf.getvalue())
with open(path, "wb") as f:
    f.write(buf.getvalue())
PYEOF
log "Normalized sdist tar entries + gzip header to SOURCE_DATE_EPOCH"

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
