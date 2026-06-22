# QiJu PyPI Packaging

Build and publish scripts for the `qiju` package on PyPI.

## Prerequisites

- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `release/` synced and up to date (`bash development/sync-release.sh`)
- Optional: `uv tool install twine` for artifact metadata verification

## Workflow

### 1. Sync release and build

```bash
# From the repo root (qiju-diarist/)
bash development/sync-release.sh
bash development/packaging/pypi/build.sh
```

This produces:
- `pypi-build/dist/qiju-<VERSION>-py3-none-any.whl`
- `pypi-build/dist/qiju-<VERSION>.tar.gz`
- `pypi-build/dist/SHA256SUMS`

`build.sh` sets `SOURCE_DATE_EPOCH` to the last `release/` git commit timestamp before
invoking `uv build`, so successive builds from the same source produce identical bytes.

### 2. Local smoke test (no upload)

```bash
bash development/packaging/pypi/publish.sh --smoke
```

Tests all four hosts (`claude`, `codex`, `kiro`, `cursor`) from the installed wheel.
Full isolation: both `HOME` and `QIJU_HOME` are exported to isolated temporary
directories — no real `~/.qiju`, `~/.claude`, `~/.codex`, `~/.kiro`, or `~/.cursor`
files are read or written.

### 3. TestPyPI (dual-index: qiju from TestPyPI, duckdb from prod PyPI)

```bash
export TESTPYPI_TOKEN="pypi-..."
bash development/packaging/pypi/publish.sh --test-pypi
```

Install from TestPyPI for manual verification:

```bash
uv pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  qiju==<VERSION>
```

### 4. Production PyPI

```bash
export PYPI_TOKEN="pypi-..."
bash development/packaging/pypi/publish.sh --prod-pypi
```

Then tag and push:

```bash
cd release/
git tag v<VERSION>
git push origin v<VERSION>
```

## Security scan

`build.sh` runs `scan.py` automatically. To run manually:

```bash
python development/packaging/pypi/scan.py pypi-build/staging
```

Three scan categories:
1. **blocked-local-identifiers** — local filesystem paths, SSH aliases
2. **credential-patterns** — email addresses, API tokens, private keys
3. (approved-public-identifiers are exemptions, not scanned for)

## File lists

`expected-wheel-files.txt` and `expected-sdist-files.txt` are **committed allowlists**.
`verify_artifact.sh` hard-fails if either is missing — there is no auto-generation
fallback. After a deliberate file-set change, regenerate them and commit the result:

```bash
bash development/packaging/pypi/generate_expected.sh pypi-build/dist <VERSION>
git diff packaging/pypi/expected-*.txt   # review before committing
```
