"""One-time migration: normalize all project names to lowercase slugs.

On a case-insensitive filesystem (macOS APFS), ``long/MyProject.jsonl`` and
``long/myproject.jsonl`` are the SAME file — so the APFS rename trick works: rename
source to lowercase target and then rewrite the entries inside. Never do a
"write merged then unlink source" when samefile() is true; that deletes the file you just
wrote.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

try:
    from . import archive as archive_mod, paths as paths_mod, util
except ImportError:  # pragma: no cover
    import archive as archive_mod  # type: ignore
    import paths as paths_mod  # type: ignore
    import util  # type: ignore

try:
    import duckdb as _duckdb  # noqa: F401
    _DUCKDB_AVAILABLE = True
except ImportError:
    _DUCKDB_AVAILABLE = False


def _rewrite_long_entries(path: Path, slug: str, *, dry_run: bool) -> dict[str, Any]:
    """Rewrite entries whose ``project`` field differs from ``slug``.

    Returns a report dict with ``path``, ``action``, ``entries_changed``.
    """
    entries = util.read_jsonl(path)
    changed = 0
    new_entries = []
    for entry in entries:
        proj = str(entry.get("project", ""))
        if proj != slug:
            changed += 1
            if not dry_run:
                entry = dict(entry)
                entry["project"] = slug
        new_entries.append(entry)
    if changed and not dry_run:
        util.write_jsonl_atomic(path, new_entries)
    return {"path": str(path), "action": "rewrite", "entries_changed": changed}


def _migrate_long_tier(
    home: Path, *, project: str | None, dry_run: bool
) -> list[dict[str, Any]]:
    """Migrate the long JSONL tier.

    For each long file whose stem differs from its lowercase slug: rename (or merge on
    true collision), then rewrite entries whose ``project`` field is wrong.
    """
    long_dir = home / "long"
    if not long_dir.exists():
        return []

    reports: list[dict[str, Any]] = []

    for source in sorted(long_dir.glob("*.jsonl")):
        slug = paths_mod.slugify_project(source.stem)

        # If a project filter is given, only process the matching project.
        if project and slug != paths_mod.slugify_project(project):
            continue

        target = long_dir / f"{slug}.jsonl"

        if source.name != target.name:
            # Names differ (mixed casing). Decide: same physical file or true collision?
            if target.exists() and source.exists() and os.path.samefile(source, target):
                # Case-insensitive FS: source IS target. Rename in-place (no data loss).
                if not dry_run:
                    source.rename(target)
                reports.append({
                    "path": str(source),
                    "target": str(target),
                    "action": "rename_samefile",
                    "entries_changed": 0,
                })
                # Continue to rewrite entries after rename.
                rewrite_path = target
            elif target.exists():
                # True collision on a case-sensitive FS: merge target + source.
                target_entries = util.read_jsonl(target)
                source_entries = util.read_jsonl(source)
                merged = util.stable_unique(target_entries + source_entries)
                if not dry_run:
                    util.write_jsonl_atomic(target, merged)
                    source.unlink()
                reports.append({
                    "path": str(source),
                    "target": str(target),
                    "action": "merge",
                    "entries_changed": len(merged) - len(target_entries),
                })
                rewrite_path = target
            else:
                # Target does not exist: simple rename.
                if not dry_run:
                    source.rename(target)
                reports.append({
                    "path": str(source),
                    "target": str(target),
                    "action": "rename",
                    "entries_changed": 0,
                })
                rewrite_path = target
        else:
            rewrite_path = source

        # Rewrite entries with wrong project field.
        rewrite_report = _rewrite_long_entries(rewrite_path, slug, dry_run=dry_run)
        if rewrite_report["entries_changed"] or rewrite_path != source:
            reports.append(rewrite_report)

    return reports


def _migrate_parquet_entries(parquet_path: Path, slug: str, *, dry_run: bool) -> dict[str, Any]:
    """Rewrite a parquet file's entries whose project field differs from slug."""
    entries = archive_mod.read_parquet(parquet_path)
    changed = 0
    new_entries = []
    for entry in entries:
        proj = str(entry.get("project", ""))
        if proj != slug:
            changed += 1
            if not dry_run:
                entry = dict(entry)
                entry["project"] = slug
        new_entries.append(entry)
    if changed and not dry_run:
        archive_mod.write_parquet_atomic(parquet_path, new_entries)
    return {"path": str(parquet_path), "action": "rewrite", "entries_changed": changed}


def _migrate_archive_tier(
    home: Path, *, project: str | None, dry_run: bool, warnings: list[str]
) -> list[dict[str, Any]]:
    """Migrate the archive Parquet tier."""
    archive_dir = home / "archive"
    if not archive_dir.exists():
        return []

    reports: list[dict[str, Any]] = []

    for source_dir in sorted(archive_dir.glob("project=*")):
        raw_name = source_dir.name.removeprefix("project=")
        slug = paths_mod.slugify_project(raw_name)

        if project and slug != paths_mod.slugify_project(project):
            continue

        target_dir = archive_dir / f"project={slug}"

        if source_dir.name != target_dir.name:
            if not _DUCKDB_AVAILABLE:
                warnings.append(
                    f"duckdb unavailable; skipping archive migration for {source_dir.name}"
                )
                continue

            if target_dir.exists() and os.path.samefile(source_dir, target_dir):
                # Case-insensitive FS: same physical dir. Rename in-place.
                if not dry_run:
                    source_dir.rename(target_dir)
                reports.append({
                    "path": str(source_dir),
                    "target": str(target_dir),
                    "action": "rename_samefile",
                })
            elif target_dir.exists():
                # True collision: merge per-month parquet files then remove source.
                for month_dir in sorted(source_dir.glob("month=*")):
                    month = month_dir.name
                    src_parquet = month_dir / "entries.parquet"
                    dst_parquet = target_dir / month / "entries.parquet"
                    if src_parquet.exists():
                        src_entries = archive_mod.read_parquet(src_parquet)
                        dst_entries = archive_mod.read_parquet(dst_parquet) if dst_parquet.exists() else []
                        merged = util.stable_unique(dst_entries + src_entries)
                        if not dry_run:
                            archive_mod.write_parquet_atomic(dst_parquet, merged)
                        reports.append({
                            "path": str(src_parquet),
                            "target": str(dst_parquet),
                            "action": "merge",
                            "entries_changed": len(merged) - len(dst_entries),
                        })
                if not dry_run:
                    shutil.rmtree(source_dir)
            else:
                # Target dir does not exist: rename the whole project dir.
                if not dry_run:
                    source_dir.rename(target_dir)
                reports.append({
                    "path": str(source_dir),
                    "target": str(target_dir),
                    "action": "rename",
                })
        else:
            target_dir = source_dir

        # Rewrite parquet entries with wrong project fields.
        if not _DUCKDB_AVAILABLE:
            parquet_files = list(target_dir.glob("month=*/entries.parquet")) if target_dir.exists() else []
            if parquet_files:
                warnings.append(
                    f"duckdb unavailable; skipping parquet entry rewrite for {target_dir.name}"
                )
            continue

        for parquet_path in sorted(target_dir.glob("month=*/entries.parquet")):
            rewrite_report = _migrate_parquet_entries(parquet_path, slug, dry_run=dry_run)
            if rewrite_report["entries_changed"]:
                reports.append(rewrite_report)

    return reports


def _migrate_short_tier(
    kedu_paths: paths_mod.KeduPaths, *, dry_run: bool
) -> dict[str, Any]:
    """Rewrite short.jsonl entries whose project field is not a lowercase slug."""
    short_path = kedu_paths.short_jsonl
    if not short_path.exists():
        return {"path": str(short_path), "action": "no_op", "entries_changed": 0}

    slug = kedu_paths.project
    entries = util.read_jsonl(short_path)
    changed = 0
    new_entries = []
    for entry in entries:
        proj = str(entry.get("project", ""))
        if proj and proj != paths_mod.slugify_project(proj):
            changed += 1
            if not dry_run:
                entry = dict(entry)
                entry["project"] = paths_mod.slugify_project(proj)
        new_entries.append(entry)
    if changed and not dry_run:
        util.write_jsonl_atomic(short_path, new_entries)
    return {"path": str(short_path), "action": "rewrite", "entries_changed": changed}


def _migrate_marker(
    kedu_paths: paths_mod.KeduPaths, *, dry_run: bool
) -> dict[str, Any]:
    """Lowercase the ``project`` key in .kedu/config.json if needed."""
    marker_path = kedu_paths.project_root / paths_mod.MARKER_REL
    if not marker_path.exists():
        return {"path": str(marker_path), "action": "no_op", "changed": False}

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(marker_path), "action": "skip_unreadable", "changed": False}

    if not isinstance(data, dict):
        return {"path": str(marker_path), "action": "skip_not_dict", "changed": False}

    raw_project = data.get("project")
    if not isinstance(raw_project, str) or not raw_project:
        return {"path": str(marker_path), "action": "no_op", "changed": False}

    lowered = paths_mod.slugify_project(raw_project)
    if raw_project == lowered:
        return {"path": str(marker_path), "action": "no_op", "changed": False}

    if not dry_run:
        updated = dict(data)
        updated["project"] = lowered
        util.write_text_atomic(marker_path, json.dumps(updated, indent=2))

    return {"path": str(marker_path), "action": "rewrite", "changed": True, "old": raw_project, "new": lowered}


def migrate_project_names(
    *,
    project: str | None = None,
    cwd: str | Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Normalize all project names to lowercase slugs across stored records.

    Migrates: long JSONL tier, archive Parquet tier, current project's short tier and
    init marker. Idempotent: a second run on an already-normalized store reports no
    changes.

    Args:
        project: If given, only migrate this project slug (applies to long and archive
                 tiers). Short tier and marker always use the resolved current project.
        cwd: Working directory for resolving the current project (defaults to os.getcwd()).
        home: Kedu home directory (defaults to KEDU_HOME / ~/.kedu).
        dry_run: When True, report planned changes without writing anything.

    Returns:
        A JSON-serialisable report dict with keys ``dry_run``, ``long``, ``archive``,
        ``short``, ``marker``, and ``warnings``.
    """
    if home is None:
        home = paths_mod.kedu_home()

    warnings: list[str] = []
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "long": [],
        "archive": [],
        "short": {},
        "marker": {},
        "warnings": warnings,
    }

    lock_path = home / ".kedu.lock"
    with util.exclusive_lock(lock_path):
        report["long"] = _migrate_long_tier(home, project=project, dry_run=dry_run)
        report["archive"] = _migrate_archive_tier(home, project=project, dry_run=dry_run, warnings=warnings)

        # Short tier and marker: always scoped to the resolved current project.
        try:
            kedu_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
        except Exception as exc:
            warnings.append(f"could not resolve current project paths: {exc}")
        else:
            report["short"] = _migrate_short_tier(kedu_paths, dry_run=dry_run)
            report["marker"] = _migrate_marker(kedu_paths, dry_run=dry_run)

    return report
