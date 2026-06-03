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
    entry_id: str | None,
) -> dict[str, Any]:
    entry = schema.normalize_entry(raw)
    entry["schema_version"] = schema.SCHEMA_VERSION
    entry["source"] = source
    entry["project"] = project
    entry["agent"] = agent or os.environ.get("KEDU_AGENT") or entry.get("agent") or "unknown"
    entry.setdefault("ts", util.utcish_now_iso())
    if not entry.get("ts"):
        entry["ts"] = util.utcish_now_iso()
    if entry_id:
        entry["id"] = entry_id
    else:
        entry.pop("id", None)
    redacted, _ = redact.redact_entry(entry)
    validation_entry = dict(redacted)
    if not validation_entry.get("id"):
        validation_entry["id"] = "__pending_id__"
    schema.validate(validation_entry)
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
    # Refuse to mint a new project identity from a wandered cwd. This fires only when the
    # root fell through to the cwd fallback (no KEDU_PROJECT_ROOT, no init marker found by
    # walking up, no git toplevel) and the caller did not name a project explicitly.
    if (
        kedu_paths.root_origin == "cwd"
        and not project
        and not (kedu_paths.project_kedu_dir / "config.json").is_file()
    ):
        raise SystemExit(
            "kedu log: could not determine the project root, so refusing to create a new "
            f"identity from {kedu_paths.project_root}.\n"
            "Run `kedu init` in your project root, pass --project <slug>, or set "
            "KEDU_PROJECT_ROOT."
        )
    paths_mod.ensure_base_dirs(kedu_paths)
    explicit_entry_id = str(raw.get("id", "")).strip() if raw.get("id") else None
    entry = prepare_entry(
        raw,
        source=source,
        project=kedu_paths.project,
        agent=agent,
        entry_id=explicit_entry_id,
    )

    with util.exclusive_lock(kedu_paths.lock_file):
        entry_id = explicit_entry_id or id_gen.make_id(kedu_paths, explicit_session_uuid=session_id)
        entry["id"] = entry_id
        schema.validate(entry)
        locations = id_locations(kedu_paths, entry_id)
        if not explicit_entry_id and locations:
            raise RuntimeError(f"generated duplicate Kedu id: {entry_id}")
        if "archive" in locations:
            return entry_id
        if "short" not in locations:
            util.append_jsonl(kedu_paths.short_jsonl, entry)
        if "long" not in locations:
            util.append_jsonl(kedu_paths.long_jsonl, entry)

    if rebuild_state:
        state.rebuild_state(project=kedu_paths.project, cwd=kedu_paths.project_root)

    return entry_id
