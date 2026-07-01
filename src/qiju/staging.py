from __future__ import annotations

import fnmatch
import os
import re
import uuid


from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import paths as paths_mod


STAGING_PREFIX = "qiju-entry."
STAGING_SUFFIX = ".json"
STAGING_GLOB = "qiju-entry.*.json"
ALLOCATE_MAX_TRIES = 8


def _agent_label(agent: str | None) -> str:
    # Fallback chain so the filename label is populated even when --agent is omitted:
    # explicit arg -> $QIJU_AGENT -> "agent". The env read lives here so every caller
    # inherits it.
    raw = (agent or os.environ.get("QIJU_AGENT") or "").strip()
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-").lower()
    return label or "agent"


def allocate_staging(
    *,
    project: str | None = None,
    cwd: str | Path | None = None,
    agent: str | None = None,
) -> Path:
    """Atomically create a unique, workspace-local staging file and return its path.

    Uniqueness comes from UUID entropy plus O_EXCL (``open(..., "x")``) — never from the
    agent label. The file is created empty; the caller writes its JSON record into it.
    """
    qiju_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    paths_mod.ensure_base_dirs(qiju_paths)
    label = _agent_label(agent)
    last_exc: OSError | None = None
    for _ in range(ALLOCATE_MAX_TRIES):
        candidate = qiju_paths.tmp_dir / f"{STAGING_PREFIX}{label}.{uuid.uuid4().hex}{STAGING_SUFFIX}"
        try:
            with open(candidate, "x", encoding="utf-8"):
                pass
            return candidate
        except FileExistsError as exc:  # astronomically unlikely; retry with fresh UUID
            last_exc = exc
            continue
    raise RuntimeError(
        f"qiju temp-entry: could not allocate a unique staging file after "
        f"{ALLOCATE_MAX_TRIES} attempts"
    ) from last_exc


def is_managed_staging_file(
    path: str | Path,
    tmp_dir: str | Path,
) -> tuple[bool, str | None, Path | None]:
    """Validate that ``path`` is a Qiju-managed staging file safe to delete.

    Returns ``(ok, reason_if_not, resolved_path)``. The resolved path is returned so
    callers unlink exactly the path the guard validated, with no second unguarded
    ``realpath``. Checks are applied in a fixed order (design §3.2.1).
    """
    # 1. Reject a symlink on the literal path, before resolving, so it cannot redirect
    #    the delete to an arbitrary target.
    if os.path.islink(path):
        return False, "is a symlink", None
    # 2. Containment: realpath must be a direct child of tmp_dir (blocks ../ escape).
    rp = Path(os.path.realpath(path))
    tmp_rp = Path(os.path.realpath(tmp_dir))
    if rp.parent != tmp_rp:
        return False, f"is not inside {tmp_rp}", None
    # 3. Name match.
    if not fnmatch.fnmatch(rp.name, STAGING_GLOB):
        return False, f"name does not match {STAGING_GLOB}", None
    # 4. Regular file (not a directory or special file).
    if not rp.is_file():
        return False, "is not a regular file", None
    return True, None, rp


def safe_cleanup(
    body_path: str | Path | None,
    *,
    project: str | None = None,
    cwd: str | Path | None = None,
) -> tuple[bool, str | None]:
    """Delete ``body_path`` only if it is a Qiju-managed staging file.

    Returns ``(deleted, reason_if_not)``. Never raises: a refused or failed delete is
    reported via the reason so the caller can warn without failing the log.
    """
    if not body_path:
        return False, "no --body file to clean up"
    qiju_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    ok, reason, rp = is_managed_staging_file(body_path, qiju_paths.tmp_dir)
    if not ok:
        return False, reason
    try:
        os.unlink(rp)  # the guard-validated path
    except OSError as exc:
        return False, str(exc)
    return True, None


def sweep_stale(
    qiju_paths: paths_mod.QijuPaths,
    *,
    now: datetime,
    ttl_hours: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Remove staging files older than ``ttl_hours`` left behind by crashed agents."""
    tmp_dir = qiju_paths.tmp_dir
    if not tmp_dir.exists():
        return {"removed": 0, "kept": 0, "ttl_hours": ttl_hours}
    cutoff = now - timedelta(hours=ttl_hours)
    removed = 0
    kept = 0
    for child in sorted(tmp_dir.glob(STAGING_GLOB)):
        ok, _reason, rp = is_managed_staging_file(child, tmp_dir)
        if not ok or rp is None:
            continue
        try:
            mtime = datetime.fromtimestamp(rp.stat().st_mtime).astimezone()
        except OSError:
            continue
        if mtime < cutoff:
            if not dry_run:
                try:
                    os.unlink(rp)
                except OSError:
                    continue
            removed += 1
        else:
            kept += 1
    return {"removed": removed, "kept": kept, "ttl_hours": ttl_hours}
