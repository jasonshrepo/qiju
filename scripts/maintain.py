from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import archive, paths as paths_mod, util
except ImportError:  # pragma: no cover
    import archive  # type: ignore
    import paths as paths_mod  # type: ignore
    import util  # type: ignore


SHORT_WINDOW_DAYS = 7
ARCHIVE_AFTER_DAYS = 92
SMALL_PARTITION_FLOOR_BYTES = 2 * 1024 * 1024
FORCE_LONG_FILE_BYTES = 50 * 1024 * 1024
FORCE_ARCHIVE_AFTER_DAYS = 31
MAX_SMALL_PARTITION_AGE_DAYS = 366


def _entry_month(entry: dict[str, Any]) -> str:
    return str(entry["ts"])[:7]


def _entry_size(entry: dict[str, Any]) -> int:
    return len(json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _older_than(entry: dict[str, Any], now: datetime, days: int) -> bool:
    return util.parse_iso(str(entry["ts"])) < now - timedelta(days=days)


def rotate_short(kedu_paths: paths_mod.KeduPaths, *, now: datetime, dry_run: bool) -> dict[str, Any]:
    entries = util.read_jsonl(kedu_paths.short_jsonl)
    keep = [entry for entry in entries if not _older_than(entry, now, SHORT_WINDOW_DAYS)]
    removed = len(entries) - len(keep)
    if removed and not dry_run:
        util.write_jsonl_atomic(kedu_paths.short_jsonl, keep)
    return {"path": str(kedu_paths.short_jsonl), "removed": removed, "kept": len(keep)}


def _write_archive_partition(
    kedu_paths: paths_mod.KeduPaths,
    month: str,
    entries: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    output_path = kedu_paths.archive_partition(month)
    existing = archive.read_parquet(output_path) if output_path.exists() else []
    merged = util.stable_unique(existing + entries)
    if not dry_run:
        archive.write_parquet_atomic(output_path, merged)
    return {"path": str(output_path), "entries": len(entries), "total_entries": len(merged)}


def archive_long_project(
    kedu_paths: paths_mod.KeduPaths,
    *,
    now: datetime,
    dry_run: bool,
) -> dict[str, Any]:
    long_entries = util.read_jsonl(kedu_paths.long_jsonl)
    if not long_entries:
        return {"project": kedu_paths.project, "archived": [], "remaining": 0, "warnings": []}

    warnings: list[str] = []
    force = kedu_paths.long_jsonl.exists() and kedu_paths.long_jsonl.stat().st_size > FORCE_LONG_FILE_BYTES
    if force:
        warnings.append(f"{kedu_paths.long_jsonl} exceeds {FORCE_LONG_FILE_BYTES} bytes; force-archiving old entries")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in long_entries:
        groups[_entry_month(entry)].append(entry)

    archived_ids: set[str] = set()
    archived: list[dict[str, Any]] = []
    for month, entries in sorted(groups.items()):
        all_older_than_archive = all(_older_than(entry, now, ARCHIVE_AFTER_DAYS) for entry in entries)
        all_older_than_force = all(_older_than(entry, now, FORCE_ARCHIVE_AFTER_DAYS) for entry in entries)
        all_older_than_max = all(_older_than(entry, now, MAX_SMALL_PARTITION_AGE_DAYS) for entry in entries)
        size = sum(_entry_size(entry) for entry in entries)
        should_archive = (
            (all_older_than_archive and size > SMALL_PARTITION_FLOOR_BYTES)
            or (all_older_than_archive and all_older_than_max)
            or (force and all_older_than_force)
        )
        if not should_archive:
            continue
        archived.append(_write_archive_partition(kedu_paths, month, entries, dry_run=dry_run) | {"size": size})
        archived_ids.update(str(entry["id"]) for entry in entries)

    if archived_ids and not dry_run:
        remaining = [entry for entry in long_entries if str(entry.get("id")) not in archived_ids]
        util.write_jsonl_atomic(kedu_paths.long_jsonl, remaining)
    else:
        remaining = long_entries

    return {
        "project": kedu_paths.project,
        "archived": archived,
        "remaining": len(remaining),
        "warnings": warnings,
    }


def maintain(
    *,
    project: str | None = None,
    cwd: str | Path | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now().astimezone()
    current_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    paths_mod.ensure_base_dirs(current_paths)

    with util.exclusive_lock(current_paths.lock_file):
        rotation = rotate_short(current_paths, now=now, dry_run=dry_run)
        projects = [current_paths.project] if project else [path.stem for path in paths_mod.all_long_files(current_paths.home)]
        if current_paths.project not in projects:
            projects.append(current_paths.project)
        archives: list[dict[str, Any]] = []
        for project_name in sorted(set(projects)):
            project_paths = paths_mod.resolve_paths(project=project_name, cwd=current_paths.project_root)
            archives.append(archive_long_project(project_paths, now=now, dry_run=dry_run))

    for item in archives:
        for warning in item.get("warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
    return {"dry_run": dry_run, "rotation": rotation, "archives": archives}

