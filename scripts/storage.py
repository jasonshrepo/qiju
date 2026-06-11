from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from . import archive, paths as paths_mod, util
except ImportError:  # pragma: no cover
    import archive  # type: ignore
    import paths as paths_mod  # type: ignore
    import util  # type: ignore


def archive_files_for_project(kedu_paths: paths_mod.KeduPaths) -> list[Path]:
    project_dir = kedu_paths.archive_dir / f"project={kedu_paths.project}"
    if not project_dir.exists():
        return []
    return sorted(project_dir.glob("month=*/entries.parquet"))


def read_archive_entries(kedu_paths: paths_mod.KeduPaths) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for parquet_path in archive_files_for_project(kedu_paths):
        entries.extend(archive.read_parquet(parquet_path))
    return entries


def read_project_entries(kedu_paths: paths_mod.KeduPaths, include_short: bool = True) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if include_short:
        entries.extend(util.read_jsonl(kedu_paths.short_jsonl))
    entries.extend(util.read_jsonl(kedu_paths.long_jsonl))
    entries.extend(read_archive_entries(kedu_paths))
    return util.stable_unique(entries)


def id_locations(kedu_paths: paths_mod.KeduPaths, entry_id: str) -> set[str]:
    locations: set[str] = set()
    if any(entry.get("id") == entry_id for entry in util.read_jsonl(kedu_paths.short_jsonl)):
        locations.add("short")
    if any(entry.get("id") == entry_id for entry in util.read_jsonl(kedu_paths.long_jsonl)):
        locations.add("long")
    for entry in read_archive_entries(kedu_paths):
        if entry.get("id") == entry_id:
            locations.add("archive")
            break
    return locations


def all_projects(home: Path | None = None) -> list[str]:
    home = home or paths_mod.kedu_home()
    # Lowercase normalizes pre-migration files so the listing is canonical even before
    # `kedu migrate` has run; dedup handles the case-insensitive FS single-file scenario.
    projects = {path.stem.lower() for path in paths_mod.all_long_files(home)}
    archive_dir = home / "archive"
    if archive_dir.exists():
        for path in archive_dir.glob("project=*"):
            projects.add(path.name.removeprefix("project=").lower())
    return sorted(projects)

