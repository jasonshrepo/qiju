#!/usr/bin/env python3
"""Cross-platform end-to-end smoke test for qiju.

Runs the real user journey (init -> temp-entry -> log -> search -> maintain) against an
isolated, throwaway QIJU_HOME/QIJU_PROJECT_ROOT, using a record whose body contains
non-ASCII text. Output is captured through a pipe, which on Windows forces the locale
(cp1252) encoding path — so this reproduces the UnicodeEncodeError class of bug if the
UTF-8 console fix regresses. Exits non-zero on any failure.

Invoke identically on any OS:
    python tests/smoke_cross_platform.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NON_ASCII = "测试 🚀 café"
PROJECT = "smoke"


def _qiju_cmd() -> list[str]:
    """Prefer the installed console script; fall back to running the package in-tree."""
    exe = shutil.which("qiju")
    if exe:
        return [exe]
    return [sys.executable, "-c", "import sys; from qiju.cli import main; sys.exit(main())"]


def run(args: list[str], env: dict) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        _qiju_cmd() + args,
        env=env,
        capture_output=True,   # pipe (not a tty) -> exercises locale encoding on Windows
        text=True,
        encoding="utf-8",
    )
    return proc


def fail(stage: str, proc: subprocess.CompletedProcess) -> None:
    print(f"SMOKE FAIL at: {stage}")
    print("  exit:", proc.returncode)
    print("  stdout:", proc.stdout)
    print("  stderr:", proc.stderr)
    sys.exit(1)


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="qiju-smoke-"))
    try:
        home = workdir / "home"
        root = workdir / "project"
        home.mkdir()
        root.mkdir()
        env = dict(os.environ)
        env["QIJU_HOME"] = str(home)
        env["QIJU_PROJECT_ROOT"] = str(root)

        # 1) init
        p = run(["init", "--host", "claude"], env)
        if p.returncode != 0:
            fail("init", p)

        # 2) temp-entry -> staging path
        p = run(["temp-entry", "--agent", "claude"], env)
        if p.returncode != 0:
            fail("temp-entry", p)
        staging_path = Path(p.stdout.strip().splitlines()[-1])
        if not staging_path.exists():
            fail("temp-entry (path missing)", p)

        # 3) write a record with non-ASCII content, then log it
        record = {
            "title": f"smoke {NON_ASCII}",
            "tags": ["smoke", "portability"],
            "search_terms": ["smoke", NON_ASCII],
            "next_steps": ["none"],
            "body_md": f"Cross-platform smoke record. Non-ASCII round-trip: {NON_ASCII}",
        }
        staging_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

        p = run(["log", "--source", "manual", "--agent", "claude",
                 "--project", PROJECT, "--body", str(staging_path), "--cleanup"], env)
        if p.returncode != 0:
            fail("log", p)
        record_id = p.stdout.strip().splitlines()[-1]
        if ":" not in record_id:
            fail("log (no record id returned)", p)

        # 4) search — assert the id and the non-ASCII content round-trip through a pipe
        p = run(["search", "--project", PROJECT, "--query", "测试", "--format", "summary"], env)
        if p.returncode != 0:
            fail("search", p)
        if record_id.split(":")[0] not in p.stdout:
            fail("search (record id not found)", p)
        if "测试" not in p.stdout:
            fail("search (non-ASCII did not round-trip)", p)

        # 5) maintain — exercises the lock + replace_atomic + parquet write/read
        p = run(["maintain"], env)
        if p.returncode != 0:
            fail("maintain", p)

        print(f"SMOKE PASS — id={record_id}, non-ASCII round-trip OK ({NON_ASCII})")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
