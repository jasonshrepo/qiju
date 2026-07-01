from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator

# File locking is platform-specific: POSIX has fcntl.flock; Windows has msvcrt.locking.
# Import only the one that exists so the module loads on both (fcntl is absent on Windows).
if os.name == "nt":
    import msvcrt
else:
    import fcntl


def utcish_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: JSONL row must be an object")
            entries.append(value)
    return entries


def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def replace_atomic(src: Path, dst: Path, attempts: int = 10, base_delay: float = 0.05) -> None:
    """``os.replace(src, dst)`` with Windows-only retry.

    On POSIX, replace-over-open-file is atomic and a PermissionError is a genuine error, so
    it propagates immediately. On Windows os.replace raises PermissionError when another
    process (antivirus, indexer, a concurrent reader) briefly holds the destination open;
    a short backoff retries past that transient hold.
    """
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or i == attempts - 1:
                raise
            time.sleep(base_delay * (i + 1))


def write_jsonl_atomic(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for entry in entries:
                line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        replace_atomic(tmp_path, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        replace_atomic(tmp_path, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()


def _acquire_lock(handle) -> None:
    """Block until an exclusive lock on ``handle`` is held (whole-file on POSIX,
    a 1-byte region at offset 0 on Windows)."""
    if os.name == "nt":
        handle.seek(0)
        # LK_LOCK retries for ~10s then raises; loop so the call blocks until acquired.
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _release_lock(handle) -> None:
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        _acquire_lock(handle)
        try:
            yield
        finally:
            _release_lock(handle)


def stable_unique(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for entry in entries:
        entry_id = str(entry.get("id", ""))
        if entry_id in seen:
            continue
        seen.add(entry_id)
        result.append(entry)
    return result


def parse_iso(ts: str):
    from datetime import datetime

    normalized = ts.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    # Stored timestamps are tz-aware; a bare date/datetime bound (e.g. `--since 2026-06-02`)
    # parses naive. Attach the local zone so range comparisons never mix naive and aware.
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def try_parse_iso(ts):
    """Parse ``ts`` like ``parse_iso`` but return ``None`` instead of raising.

    Returns a tz-aware ``datetime`` when ``ts`` is a parseable ISO 8601 string,
    otherwise ``None`` (non-string input or unparseable value).
    """
    if not isinstance(ts, str):
        return None
    try:
        return parse_iso(ts)
    except (ValueError, TypeError):
        return None


def jsonable_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))
