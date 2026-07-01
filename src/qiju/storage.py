from __future__ import annotations

from pathlib import Path
from typing import Any

from . import archive, paths as paths_mod, util


def archive_files_for_project(qiju_paths: paths_mod.QijuPaths) -> list[Path]:
    project_dir = qiju_paths.archive_dir / f"project={qiju_paths.project}"
    if not project_dir.exists():
        return []
    return sorted(project_dir.glob("month=*/entries.parquet"))


def read_archive_entries(qiju_paths: paths_mod.QijuPaths) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for parquet_path in archive_files_for_project(qiju_paths):
        entries.extend(archive.read_parquet(parquet_path))
    return entries


def read_project_entries(qiju_paths: paths_mod.QijuPaths, include_short: bool = True) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if include_short:
        entries.extend(util.read_jsonl(qiju_paths.short_jsonl))
    entries.extend(util.read_jsonl(qiju_paths.long_jsonl))
    entries.extend(read_archive_entries(qiju_paths))
    return util.stable_unique(entries)


def id_locations(qiju_paths: paths_mod.QijuPaths, entry_id: str) -> set[str]:
    locations: set[str] = set()
    if any(entry.get("id") == entry_id for entry in util.read_jsonl(qiju_paths.short_jsonl)):
        locations.add("short")
    if any(entry.get("id") == entry_id for entry in util.read_jsonl(qiju_paths.long_jsonl)):
        locations.add("long")
    for entry in read_archive_entries(qiju_paths):
        if entry.get("id") == entry_id:
            locations.add("archive")
            break
    return locations


def all_projects(home: Path | None = None) -> list[str]:
    home = home or paths_mod.qiju_home()
    # Lowercase normalizes pre-migration files so the listing is canonical even before
    # `qiju migrate` has run; dedup handles the case-insensitive FS single-file scenario.
    projects = {path.stem.lower() for path in paths_mod.all_long_files(home)}
    archive_dir = home / "archive"
    if archive_dir.exists():
        for path in archive_dir.glob("project=*"):
            projects.add(path.name.removeprefix("project=").lower())
    return sorted(projects)

