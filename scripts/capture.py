from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from . import id_gen, paths as paths_mod, redact, schema, state, util
    from .storage import id_locations
except ImportError:  # pragma: no cover
    import id_gen  # type: ignore
    import paths as paths_mod  # type: ignore
    import redact  # type: ignore
    import schema  # type: ignore
    import state  # type: ignore
    import util  # type: ignore
    from storage import id_locations  # type: ignore


def read_entry(body_path: str | None = None, stdin_text: str | None = None) -> dict[str, Any]:
    if body_path:
        text = Path(body_path).read_text(encoding="utf-8")
    else:
        text = stdin_text if stdin_text is not None else sys.stdin.read()
    if not text.strip():
        raise ValueError("kedu log requires a JSON record via --body or stdin")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("entry JSON must be an object")
    return value


def prepare_entry(
    raw: dict[str, Any],
    *,
    source: str,
    project: str,
    agent: str | None,
    kedu_paths: paths_mod.KeduPaths,
    session_id: str | None = None,
) -> dict[str, Any]:
    entry = schema.normalize_entry(raw)
    entry["schema_version"] = schema.SCHEMA_VERSION
    entry["source"] = source
    entry["project"] = project
    entry["agent"] = agent or os.environ.get("KEDU_AGENT") or entry.get("agent") or "unknown"
    entry.setdefault("ts", util.utcish_now_iso())
    if not entry.get("ts"):
        entry["ts"] = util.utcish_now_iso()
    if not entry.get("id"):
        entry["id"] = id_gen.make_id(kedu_paths, explicit_session_uuid=session_id)
    redacted, _ = redact.redact_entry(entry)
    schema.validate(redacted)
    return redacted


def log_entry(
    raw: dict[str, Any],
    *,
    source: str,
    project: str | None = None,
    agent: str | None = None,
    cwd: str | Path | None = None,
    session_id: str | None = None,
    rebuild_state: bool = True,
) -> str:
    kedu_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    paths_mod.ensure_base_dirs(kedu_paths)
    entry = prepare_entry(
        raw,
        source=source,
        project=kedu_paths.project,
        agent=agent,
        kedu_paths=kedu_paths,
        session_id=session_id,
    )

    with util.exclusive_lock(kedu_paths.lock_file):
        locations = id_locations(kedu_paths, entry["id"])
        if "archive" in locations:
            return entry["id"]
        if "short" not in locations:
            util.append_jsonl(kedu_paths.short_jsonl, entry)
        if "long" not in locations:
            util.append_jsonl(kedu_paths.long_jsonl, entry)

        if rebuild_state:
            state.rebuild_state(project=kedu_paths.project, cwd=kedu_paths.project_root)

    return entry["id"]
