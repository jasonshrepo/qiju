from __future__ import annotations

import os
import uuid
from pathlib import Path

try:
    from . import storage, util
except ImportError:  # pragma: no cover
    import storage  # type: ignore
    import util  # type: ignore


def session_uuid(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for key in ("QIJU_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "KIRO_SESSION_ID"):
        value = os.environ.get(key)
        if value:
            return value
    return str(uuid.uuid4())


def next_seq(paths, session_id: str) -> int:
    prefix = f"{session_id}:"
    max_seq = 0
    entries = []
    for path in (paths.short_jsonl, paths.long_jsonl):
        entries.extend(util.read_jsonl(path))
    entries.extend(storage.read_archive_entries(paths))
    for entry in entries:
        entry_id = str(entry.get("id", ""))
        if not entry_id.startswith(prefix):
            continue
        suffix = entry_id[len(prefix) :]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return max_seq + 1


def make_id(paths, explicit_session_uuid: str | None = None, explicit_seq: int | None = None) -> str:
    sid = session_uuid(explicit_session_uuid)
    seq = explicit_seq if explicit_seq is not None else next_seq(paths, sid)
    return f"{sid}:{seq}"
