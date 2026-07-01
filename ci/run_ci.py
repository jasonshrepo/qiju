#!/usr/bin/env python3
"""Fixed, cross-platform CI runner for qiju.

All CI logic lives here (not in the workflow YAML) so it runs identically on GitHub's
cloud runners and on a developer's machine. It resolves the repo root as the nearest
ancestor containing ``tests/`` — so the same file works whether it sits at
``development/ci/run_ci.py`` or at the promoted ``release/ci/run_ci.py``.

Stages (stop at the first failure, non-zero exit):
  1. import qiju + ``qiju --version``   (catches the fcntl import crash on Windows)
  2. full pytest suite                   (Unix regression gate + Windows proof)
  3. cross-platform smoke test           (real journey incl. non-ASCII through a pipe)

Run identically anywhere:
    python ci/run_ci.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "tests").is_dir():
            return parent
    print("run_ci: could not locate a 'tests/' directory above this script", file=sys.stderr)
    raise SystemExit(2)


def run_stage(name: str, argv: list[str], cwd: Path) -> None:
    print("\n=== run_ci: %s ===" % name, flush=True)
    result = subprocess.run(argv, cwd=str(cwd))
    if result.returncode != 0:
        print("run_ci: FAIL at '%s' (exit %d)" % (name, result.returncode), file=sys.stderr)
        raise SystemExit(result.returncode)
    print("run_ci: PASS %s" % name, flush=True)


def main() -> int:
    root = find_root()
    print("run_ci: repo root =", root, flush=True)
    stages = [
        (
            "import + version",
            [sys.executable, "-c",
             "import qiju, sys; from qiju.cli import main; sys.argv=['qiju','--version']; sys.exit(main())"],
        ),
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("smoke", [sys.executable, "tests/smoke_cross_platform.py"]),
    ]
    for name, argv in stages:
        run_stage(name, argv, root)
    print("\nrun_ci: ALL STAGES PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
