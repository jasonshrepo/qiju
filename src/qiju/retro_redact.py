from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from . import archive, paths as paths_mod, redact, storage, util
except ImportError:  # pragma: no cover
    import archive  # type: ignore
    import paths as paths_mod  # type: ignore
    import redact  # type: ignore
    import storage  # type: ignore
    import util  # type: ignore


def _rewrite_jsonl(path: Path, value: str, placeholder: str) -> int:
    entries = util.read_jsonl(path)
    changed_entries = []
    changed_count = 0
    for entry in entries:
        changed_entry, changed = redact.replace_literal_in_entry(entry, value, placeholder)
        changed_entries.append(changed_entry)
        if changed:
            changed_count += 1
    if changed_count:
        util.write_jsonl_atomic(path, changed_entries)
    return changed_count


def redact_value_everywhere(
    *,
    value: str,
    reason: str,
    placeholder: str = "[REDACTED:manual]",
    project: str | None = None,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    if not value or not value.strip():
        raise ValueError(
            "redact value must be a non-empty, non-whitespace string; an empty value is "
            "'contained' in every string and would inject the placeholder between every "
            "character of every field, corrupting all records"
        )
    qiju_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    paths_mod.ensure_base_dirs(qiju_paths)
    changes: list[dict[str, Any]] = []
    with util.exclusive_lock(qiju_paths.lock_file):
        short_count = _rewrite_jsonl(qiju_paths.short_jsonl, value, placeholder)
        if short_count:
            changes.append({"tier": "short", "path": str(qiju_paths.short_jsonl), "entries": short_count})

        for long_path in paths_mod.all_long_files(qiju_paths.home):
            count = _rewrite_jsonl(long_path, value, placeholder)
            if count:
                changes.append({"tier": "long", "path": str(long_path), "entries": count})

        for project_dir in sorted(qiju_paths.archive_dir.glob("project=*")) if qiju_paths.archive_dir.exists() else []:
            for parquet_path in sorted(project_dir.glob("month=*/entries.parquet")):
                entries = archive.read_parquet(parquet_path)
                changed_entries = []
                changed_count = 0
                for entry in entries:
                    changed_entry, changed = redact.replace_literal_in_entry(entry, value, placeholder)
                    changed_entries.append(changed_entry)
                    if changed:
                        changed_count += 1
                if changed_count:
                    archive.write_parquet_atomic(parquet_path, changed_entries)
                    changes.append({"tier": "archive", "path": str(parquet_path), "entries": changed_count})

        event = {
            "ts": util.utcish_now_iso(),
            "reason": reason,
            "placeholder": placeholder,
            "change_count": sum(item["entries"] for item in changes),
            "changes": changes,
        }
        redacted_event, _ = redact.redact_value(event, "redaction_log")
        util.append_jsonl(qiju_paths.redaction_log, redacted_event)
    return event

