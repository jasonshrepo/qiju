from __future__ import annotations

import hashlib
import json
import os
import uuid


from pathlib import Path

from . import paths as paths_mod


REGISTER_SCHEMA_VERSION = 1
LEGACY_REGISTER_FILENAME = "project-register.json"
REGISTRY_DIR_NAME = "registry.d"


def registry_dir() -> Path:
    return paths_mod.qiju_home() / REGISTRY_DIR_NAME


def register_path() -> Path:
    """Back-compat name. The registry is now a directory of per-project files."""
    return registry_dir()


def _entry_filename(resolved_path: str) -> str:
    digest = hashlib.sha256(resolved_path.encode("utf-8")).hexdigest()[:32]
    return f"{digest}.json"


def _entry_path(resolved_path: str) -> Path:
    return registry_dir() / _entry_filename(resolved_path)


def _write_entry(resolved_path: str, slug: str) -> None:
    """Atomically publish one project entry to its own file.

    Each writer targets a filename derived from its own resolved path and stages
    through a process/uuid-unique temp file, so concurrent writers never share a
    temp path and never read-modify-write a shared structure. No lock needed.
    """
    registry_dir().mkdir(parents=True, exist_ok=True)
    target = _entry_path(resolved_path)
    data = {
        "schema_version": REGISTER_SCHEMA_VERSION,
        "path": resolved_path,
        "slug": slug,
    }
    tmp = target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _migrate_legacy_if_needed() -> None:
    """One-time, lazy import of the old single-file registry into per-project files.

    Best-effort and idempotent: guarded by renaming the legacy file to
    ``*.migrated`` and by per-entry existence checks, so a concurrent
    double-migration is harmless.
    """
    legacy = paths_mod.qiju_home() / LEGACY_REGISTER_FILENAME
    if not legacy.exists():
        return
    try:
        loaded = json.loads(legacy.read_text(encoding="utf-8"))
        projects = loaded.get("projects", {}) if isinstance(loaded, dict) else {}
    except (OSError, json.JSONDecodeError):
        projects = {}
    if not isinstance(projects, dict):
        projects = {}
    registry_dir().mkdir(parents=True, exist_ok=True)
    for path_str, slug in projects.items():
        if isinstance(path_str, str) and isinstance(slug, str):
            if not _entry_path(path_str).exists():
                _write_entry(path_str, slug)
    try:
        legacy.rename(legacy.with_name(legacy.name + ".migrated"))
    except OSError:  # pragma: no cover - already moved by a concurrent migrator
        pass


def read_registry() -> dict[str, str]:
    _migrate_legacy_if_needed()
    out: dict[str, str] = {}
    d = registry_dir()
    if not d.is_dir():
        return out
    for entry in d.iterdir():
        if entry.suffix != ".json" or not entry.is_file():
            continue  # skip *.tmp leftovers and unrelated files
        try:
            loaded = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # skip an unreadable/corrupt entry, never crash the read
        if not isinstance(loaded, dict):
            continue
        path = loaded.get("path")
        slug = loaded.get("slug")
        if isinstance(path, str) and isinstance(slug, str):
            out[path] = slug
    return out


def register_project(project_root: str | Path, slug: str) -> None:
    key = str(Path(project_root).expanduser().resolve())
    _migrate_legacy_if_needed()
    _write_entry(key, slug)


def unregister_project(project_root: str | Path) -> bool:
    key = str(Path(project_root).expanduser().resolve())
    _migrate_legacy_if_needed()
    try:
        _entry_path(key).unlink()
        return True
    except FileNotFoundError:
        return False


def registered_roots(*, prune: bool = True) -> tuple[list[Path], list[str]]:
    projects = read_registry()
    live: list[Path] = []
    pruned: list[str] = []
    for path_str in projects:
        root = Path(path_str)
        if (root / ".qiju" / "config.json").exists():
            live.append(root)
        else:
            pruned.append(path_str)
            if prune:
                try:
                    _entry_path(path_str).unlink()  # remove only this entry's file
                except FileNotFoundError:
                    pass
    return live, pruned
