#!/usr/bin/env bash
# Regenerate expected-wheel-files.txt and expected-sdist-files.txt from a built artifact.
# Run this deliberately after a file-set change, review the diff, then commit the updates.
# Usage: bash packaging/pypi/generate_expected.sh <dist_dir> <version>
set -euo pipefail

DIST_DIR="${1:?Usage: generate_expected.sh <dist_dir> <version>}"
VERSION="${2:?Usage: generate_expected.sh <dist_dir> <version>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WHEEL="$DIST_DIR/qiju-${VERSION}-py3-none-any.whl"
SDIST="$DIST_DIR/qiju-${VERSION}.tar.gz"

[ -f "$WHEEL" ] || { echo "ERROR: Wheel not found: $WHEEL" >&2; exit 1; }
[ -f "$SDIST" ] || { echo "ERROR: Sdist not found: $SDIST" >&2; exit 1; }

python3 -c "
import zipfile
with zipfile.ZipFile('$WHEEL') as z:
    names = [n for n in z.namelist() if not n.endswith('/')]
    print('\n'.join(names))
" | LC_ALL=C sort > "$SCRIPT_DIR/expected-wheel-files.txt"
echo "Written: $SCRIPT_DIR/expected-wheel-files.txt"

tar tzf "$SDIST" | grep -v '/$' | LC_ALL=C sort > "$SCRIPT_DIR/expected-sdist-files.txt"
echo "Written: $SCRIPT_DIR/expected-sdist-files.txt"

echo ""
echo "Review the updated lists with: git diff packaging/pypi/expected-*.txt"
echo "Commit when confirmed correct."
