from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The init-only marker that anchors a project root. `kedu init` writes it; `kedu log`
# never does, so stray `.kedu/` data dirs left in subfolders cannot hijack resolution.
MARKER_REL = Path(".kedu") / "config.json"


def kedu_home() -> Path:
    return Path(os.environ.get("KEDU_HOME", "~/.kedu")).expanduser()


def _find_root_marker(start: Path) -> Path | None:
    """Nearest ancestor (including start) that contains the init marker."""
    for parent in (start, *start.parents):
        if (parent / MARKER_REL).is_file():
            return parent
    return None


def _git_toplevel(start: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            check=True,
            capture_output=True,
            text=True,
        )
        root = proc.stdout.strip()
        if root:
            return Path(root).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None


def resolve_root(cwd: str | Path | None = None) -> tuple[Path, str]:
    """Resolve the project root and report its origin.

    Precedence: KEDU_PROJECT_ROOT env > nearest `.kedu/config.json` marker > git
    toplevel > cwd fallback. The origin lets callers (notably `kedu log`) refuse to
    silently mint a new identity from a wandered cwd.
    """
    start = Path(cwd or os.getcwd()).resolve()
    env = os.environ.get("KEDU_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve(), "env"
    marker = _find_root_marker(start)
    if marker is not None:
        return marker, "marker"
    git = _git_toplevel(start)
    if git is not None:
        return git, "git"
    return start, "cwd"


def project_root(cwd: str | Path | None = None) -> Path:
    return resolve_root(cwd)[0]


def _read_marker_slug(root: Path) -> str | None:
    """Canonical slug recorded in the root's init marker, if present and valid."""
    try:
        loaded = json.loads((root / MARKER_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    project = loaded.get("project") if isinstance(loaded, dict) else None
    return project if isinstance(project, str) and project else None


def slugify_project(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("project name cannot be empty")
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "project"


def project_slug(project: str | None = None, cwd: str | Path | None = None) -> str:
    if project:
        return slugify_project(project)
    root, origin = resolve_root(cwd)
    marker_slug = _read_marker_slug(root) if origin == "marker" else None
    return slugify_project(marker_slug) if marker_slug else slugify_project(root.name)


@dataclass(frozen=True)
class KeduPaths:
    project: str
    project_root: Path
    home: Path
    root_origin: str = "cwd"

    @property
    def project_kedu_dir(self) -> Path:
        return self.project_root / ".kedu"

    @property
    def short_jsonl(self) -> Path:
        return self.project_kedu_dir / "short.jsonl"

    @property
    def long_dir(self) -> Path:
        return self.home / "long"

    @property
    def long_jsonl(self) -> Path:
        return self.long_dir / f"{self.project}.jsonl"

    @property
    def archive_dir(self) -> Path:
        return self.home / "archive"

    @property
    def redaction_log(self) -> Path:
        return self.home / "redaction_log.jsonl"

    @property
    def lock_file(self) -> Path:
        return self.home / ".kedu.lock"

    def archive_partition(self, month: str) -> Path:
        return self.archive_dir / f"project={self.project}" / f"month={month}" / "entries.parquet"


def resolve_paths(project: str | None = None, cwd: str | Path | None = None) -> KeduPaths:
    root, origin = resolve_root(cwd)
    if project:
        slug = slugify_project(project)
    else:
        # Prefer the slug recorded at init so it stays stable across directory renames;
        # fall back to the directory name only when no marker is present.
        marker_slug = _read_marker_slug(root) if origin == "marker" else None
        slug = slugify_project(marker_slug) if marker_slug else slugify_project(root.name)
    return KeduPaths(project=slug, project_root=root, home=kedu_home(), root_origin=origin)


def ensure_base_dirs(paths: KeduPaths) -> None:
    paths.project_kedu_dir.mkdir(parents=True, exist_ok=True)
    paths.long_dir.mkdir(parents=True, exist_ok=True)
    paths.archive_dir.mkdir(parents=True, exist_ok=True)


def all_long_files(home: Path | None = None) -> list[Path]:
    long_dir = (home or kedu_home()) / "long"
    if not long_dir.exists():
        return []
    return sorted(long_dir.glob("*.jsonl"))
