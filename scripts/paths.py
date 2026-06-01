from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


def kedu_home() -> Path:
    return Path(os.environ.get("KEDU_HOME", "~/.kedu")).expanduser()


def project_root(cwd: str | Path | None = None) -> Path:
    start = Path(cwd or os.getcwd()).resolve()
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
    return start


def slugify_project(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("project name cannot be empty")
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "project"


def project_slug(project: str | None = None, cwd: str | Path | None = None) -> str:
    if project:
        return slugify_project(project)
    root = project_root(cwd)
    return slugify_project(root.name)


@dataclass(frozen=True)
class KeduPaths:
    project: str
    project_root: Path
    home: Path

    @property
    def project_kedu_dir(self) -> Path:
        return self.project_root / ".kedu"

    @property
    def short_jsonl(self) -> Path:
        return self.project_kedu_dir / "short.jsonl"

    @property
    def state_md(self) -> Path:
        return self.project_kedu_dir / "STATE.md"

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
    def query_log(self) -> Path:
        return self.home / "query_log.jsonl"

    @property
    def redaction_log(self) -> Path:
        return self.home / "redaction_log.jsonl"

    @property
    def lock_file(self) -> Path:
        return self.home / ".kedu.lock"

    def archive_partition(self, month: str) -> Path:
        return self.archive_dir / f"project={self.project}" / f"month={month}" / "entries.parquet"


def resolve_paths(project: str | None = None, cwd: str | Path | None = None) -> KeduPaths:
    root = project_root(cwd)
    slug = project_slug(project, root)
    return KeduPaths(project=slug, project_root=root, home=kedu_home())


def ensure_base_dirs(paths: KeduPaths) -> None:
    paths.project_kedu_dir.mkdir(parents=True, exist_ok=True)
    paths.long_dir.mkdir(parents=True, exist_ok=True)
    paths.archive_dir.mkdir(parents=True, exist_ok=True)


def all_long_files(home: Path | None = None) -> list[Path]:
    long_dir = (home or kedu_home()) / "long"
    if not long_dir.exists():
        return []
    return sorted(long_dir.glob("*.jsonl"))
