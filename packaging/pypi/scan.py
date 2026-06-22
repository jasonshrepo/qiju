#!/usr/bin/env python3
"""Three-category leak scanner for the PyPI staging tree.

Usage:
    python packaging/pypi/scan.py <staging_dir>

Exits 0 if clean, 1 if any issues are found.

Categories:
  1. blocked-local-identifiers   — substrings that must never appear in wheel source
  2. credential-patterns         — regex patterns for tokens, keys, emails
  3. (approved-public-identifiers are NOT scanned for; they are exemptions for category 2)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PACKAGING_DIR = Path(__file__).resolve().parent
SKIP_EXTENSIONS = {".pyc", ".pyo", ".duckdb", ".db", ".so", ".dylib", ".dll", ".exe"}
SKIP_DIRS = {"__pycache__", ".git"}

# Allowlisted substrings that a credential pattern might match but are safe.
# These are patterns that appear in redaction_rules.json or init_cmd.py as examples/docs.
_ALLOWLISTED_SNIPPETS = [
    "example@",
    "user@example",
    "user@host",
    "@example.com",
    "sender@",
    "recipient@",
]


def _load_blocked(path: Path) -> list[str]:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _load_credential_patterns(path: Path) -> list[tuple[str, re.Pattern[str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(item["name"], re.compile(item["pattern"])) for item in data]


def _is_allowlisted(match: str) -> bool:
    low = match.lower()
    return any(snippet.lower() in low for snippet in _ALLOWLISTED_SNIPPETS)


def _scan_file(
    path: Path,
    blocked: list[str],
    cred_patterns: list[tuple[str, re.Pattern[str]]],
) -> list[str]:
    issues = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        issues.append(f"  UNREADABLE {path}: {exc}")
        return issues

    for identifier in blocked:
        if identifier in text:
            issues.append(f"  BLOCKED-IDENTIFIER [{identifier}] in {path}")

    for name, pattern in cred_patterns:
        for match in pattern.finditer(text):
            matched_text = match.group(0)
            if not _is_allowlisted(matched_text):
                lineno = text[: match.start()].count("\n") + 1
                issues.append(f"  CREDENTIAL-PATTERN [{name}] at {path}:{lineno}: {matched_text[:60]!r}")

    return issues


def scan(staging_dir: Path) -> list[str]:
    blocked = _load_blocked(PACKAGING_DIR / "blocked_local_identifiers.txt")
    cred_patterns = _load_credential_patterns(PACKAGING_DIR / "credential_patterns.json")

    all_issues: list[str] = []
    for fpath in sorted(staging_dir.rglob("*")):
        if fpath.is_dir():
            if fpath.name in SKIP_DIRS:
                continue
        elif fpath.suffix in SKIP_EXTENSIONS:
            continue
        elif fpath.is_file():
            issues = _scan_file(fpath, blocked, cred_patterns)
            all_issues.extend(issues)

    return all_issues


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <staging_dir>", file=sys.stderr)
        return 2
    staging_dir = Path(sys.argv[1])
    if not staging_dir.is_dir():
        print(f"Not a directory: {staging_dir}", file=sys.stderr)
        return 2

    print(f"Scanning {staging_dir} ...")
    issues = scan(staging_dir)
    if issues:
        print(f"SCAN FAILED — {len(issues)} issue(s):")
        for issue in issues:
            print(issue)
        return 1

    print("Scan passed — no blocked identifiers or credential patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
