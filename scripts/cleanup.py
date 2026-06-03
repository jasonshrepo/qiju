from __future__ import annotations

import os
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .block_format import (
        CLAUDE_BLOCK_START,
        CLAUDE_BLOCK_STOP_PREFIX,
        KEDU_BLOCK_END,
        KEDU_BLOCK_START,
        find_line_marked_block,
    )
    from . import paths as paths_mod, util
except ImportError:  # pragma: no cover
    from block_format import (  # type: ignore
        CLAUDE_BLOCK_START,
        CLAUDE_BLOCK_STOP_PREFIX,
        KEDU_BLOCK_END,
        KEDU_BLOCK_START,
        find_line_marked_block,
    )
    import paths as paths_mod  # type: ignore
    import util  # type: ignore


DEFAULT_SCAN_DEPTH = 8
HOSTS = ("claude", "kiro", "codex", "cursor")
SCAN_SKIP_DIRS = {
    ".cache",
    ".git",
    ".hg",
    ".kedu",
    ".memory",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "Library",
    "node_modules",
    "site-packages",
    "vendor",
}


@dataclass
class CleanupAction:
    action: str
    path: str
    reason: str
    executed: bool = False


@dataclass
class CleanupResult:
    dry_run: bool
    actions: list[CleanupAction] = field(default_factory=list)
    preserved: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "actions": [action.__dict__ for action in self.actions],
            "preserved": self.preserved,
            "warnings": self.warnings,
        }


def _add_action(result: CleanupResult, action: str, path: Path, reason: str, *, dry_run: bool) -> None:
    result.actions.append(CleanupAction(action=action, path=str(path), reason=reason, executed=not dry_run))


def _remove_file(path: Path, result: CleanupResult, reason: str, *, dry_run: bool) -> None:
    if not path.exists():
        return
    _add_action(result, "remove_file", path, reason, dry_run=dry_run)
    if not dry_run:
        path.unlink()


def _remove_dir(path: Path, result: CleanupResult, reason: str, *, dry_run: bool) -> None:
    if not path.exists():
        return
    _add_action(result, "remove_dir", path, reason, dry_run=dry_run)
    if not dry_run:
        shutil.rmtree(path)


def _contains_path(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _remove_file_if_contains(path: Path, needle: str, result: CleanupResult, reason: str, *, dry_run: bool) -> None:
    if not path.exists() or not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        result.warnings.append(f"skip non-text file: {path}")
        return
    if needle not in content:
        result.preserved.append({"path": str(path), "reason": "file does not look Kedu-owned"})
        return
    _remove_file(path, result, reason, dry_run=dry_run)


def _remove_kedu_block(path: Path, result: CleanupResult, *, dry_run: bool) -> None:
    if not path.exists() or not path.is_file():
        return
    content = path.read_text(encoding="utf-8")
    line_marked = find_line_marked_block(content)
    if line_marked:
        start, end = line_marked
    else:
        start = content.find(KEDU_BLOCK_START)
        end = content.find(KEDU_BLOCK_END)
        if start != -1 and end != -1 and end >= start:
            end += len(KEDU_BLOCK_END)
        else:
            start = end = -1
    if start == -1 or end == -1 or end < start:
        result.preserved.append({"path": str(path), "reason": "no Kedu block found"})
        return
    updated = (content[:start].rstrip() + "\n\n" + content[end:].lstrip()).strip() + "\n"
    _add_action(result, "remove_kedu_block", path, "remove generated Kedu instruction block", dry_run=dry_run)
    if not dry_run:
        if updated.strip():
            path.write_text(updated, encoding="utf-8")
        else:
            path.unlink()


def _newest_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    newest = path.stat().st_mtime
    if path.is_dir():
        for item in path.rglob("*"):
            try:
                newest = max(newest, item.stat().st_mtime)
            except FileNotFoundError:
                continue
    return datetime.fromtimestamp(newest).astimezone()


def _entry_count(path: Path) -> int:
    return len(util.read_jsonl(path))


def _project_slug_from_config(project_root: Path, project: str | None) -> str | None:
    if project:
        return project
    config_path = project_root / ".kedu" / "config.json"
    if not config_path.exists():
        return None
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict) and isinstance(loaded.get("project"), str):
        return loaded["project"]
    return None


def _prune_project_kedu_to_short(kedu_paths: paths_mod.KeduPaths, result: CleanupResult, *, dry_run: bool) -> None:
    if not kedu_paths.project_kedu_dir.exists():
        result.preserved.append({"path": str(kedu_paths.project_kedu_dir), "reason": "project .kedu directory does not exist"})
        return

    short_count = _entry_count(kedu_paths.short_jsonl)
    long_count = _entry_count(kedu_paths.long_jsonl)
    if long_count:
        result.preserved.append({"path": str(kedu_paths.long_jsonl), "reason": f"global long records are never removed by uninstall: long={long_count}"})

    if short_count:
        for child in kedu_paths.project_kedu_dir.iterdir():
            if child.name == "short.jsonl":
                continue
            reason = "remove generated project .kedu metadata; preserve short records"
            if child.is_dir():
                _remove_dir(child, result, reason, dry_run=dry_run)
            else:
                _remove_file(child, result, reason, dry_run=dry_run)
        result.preserved.append({"path": str(kedu_paths.short_jsonl), "reason": f"preserve project short records: short={short_count}"})
        return

    _remove_dir(
        kedu_paths.project_kedu_dir,
        result,
        "remove project .kedu metadata; no local short records (global long/archive preserved)",
        dry_run=dry_run,
    )


def cleanup_user_install(
    result: CleanupResult,
    *,
    bin_dir: Path,
    install_root: Path,
    kedu_home: Path,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    shim = bin_dir / "kedu"
    if shim.exists():
        try:
            content = shim.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = ""
        if str(install_root) in content or ".venv/bin/kedu" in content:
            _remove_file(shim, result, "remove Kedu CLI shim", dry_run=dry_run)
        else:
            result.preserved.append({"path": str(shim), "reason": "kedu shim does not look owned by this install"})

    if install_root.resolve() == kedu_home.resolve() or _contains_path(install_root, kedu_home):
        result.preserved.append(
            {
                "path": str(install_root),
                "reason": "install root overlaps Kedu home; refusing to remove possible records",
            }
        )
    else:
        _remove_dir(install_root, result, "remove installed Kedu engine", dry_run=dry_run)
    for child in ("adapters", "agents", "logs"):
        _remove_dir(kedu_home / child, result, "remove installed Kedu support templates", dry_run=dry_run)

    launch_agents = Path.home() / "Library" / "LaunchAgents"
    if launch_agents.exists():
        for plist in launch_agents.glob("*.kedu*.plist"):
            _remove_file_if_contains(plist, "kedu", result, "remove Kedu launchd maintenance job", dry_run=dry_run)

    if "codex" in hosts:
        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        agent_home = Path(os.environ.get("AGENT_HOME", "~")).expanduser()
        _remove_kedu_block(codex_home / "AGENTS.md", result, dry_run=dry_run)
        _remove_dir(codex_home / "skills" / "kedu", result, "remove legacy global Codex Kedu skill", dry_run=dry_run)
        _remove_dir(agent_home / ".agents" / "skills" / "kedu", result, "remove global Codex Kedu skill", dry_run=dry_run)
    if "claude" in hosts:
        claude_home = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
        _remove_kedu_block(claude_home / "CLAUDE.md", result, dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "kedu", result, "remove Claude Kedu skill", dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "kedu-log", result, "remove Claude Kedu log skill", dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "kedu-search", result, "remove Claude Kedu search skill", dry_run=dry_run)
    if "kiro" in hosts:
        kiro_home = Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser()
        _remove_file_if_contains(kiro_home / "steering" / "kedu.md", "Kedu", result, "remove global Kiro Kedu steering", dry_run=dry_run)
        _remove_file_if_contains(kiro_home / "agents" / "kedu.json", "Kedu", result, "remove global Kiro Kedu CLI agent", dry_run=dry_run)
        _remove_file_if_contains(kiro_home / "prompts" / "kedu-agent-prompt.md", "Kedu", result, "remove global Kiro Kedu prompt", dry_run=dry_run)
        _remove_dir(kiro_home / "skills" / "kedu", result, "remove global Kiro Kedu skill", dry_run=dry_run)
    if "cursor" in hosts:
        cursor_home = Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser()
        _remove_file_if_contains(cursor_home / "rules" / "kedu.mdc", "Kedu", result, "remove global Cursor Kedu rule", dry_run=dry_run)

    for preserved_name in ("long", "archive", "query_log.jsonl", "redaction_log.jsonl"):
        path = kedu_home / preserved_name
        if path.exists():
            result.preserved.append({"path": str(path), "reason": "Kedu records/audit data are never removed by uninstall"})


def cleanup_project_install(
    result: CleanupResult,
    *,
    project_root: Path,
    project: str | None,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    resolved_project = _project_slug_from_config(project_root, project)
    kedu_paths = paths_mod.resolve_paths(project=resolved_project, cwd=project_root)

    if "codex" in hosts:
        _remove_kedu_block(project_root / "AGENTS.md", result, dry_run=dry_run)
        _remove_dir(project_root / ".agents" / "skills" / "kedu", result, "remove project Codex Kedu skill", dry_run=dry_run)
    if "claude" in hosts:
        _remove_kedu_block(project_root / "CLAUDE.md", result, dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "kedu", result, "remove project Claude Kedu skill", dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "kedu-log", result, "remove project Claude Kedu log skill", dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "kedu-search", result, "remove project Claude Kedu search skill", dry_run=dry_run)
    if "kiro" in hosts:
        _remove_file_if_contains(project_root / ".kiro" / "steering" / "kedu.md", "Kedu", result, "remove project Kiro Kedu steering", dry_run=dry_run)
        _remove_file_if_contains(project_root / ".kiro" / "agents" / "kedu.json", "Kedu", result, "remove project Kiro Kedu CLI agent", dry_run=dry_run)
        _remove_file_if_contains(project_root / ".kiro" / "prompts" / "kedu-agent-prompt.md", "Kedu", result, "remove project Kiro Kedu prompt", dry_run=dry_run)
        _remove_dir(project_root / ".kiro" / "skills" / "kedu", result, "remove project Kiro Kedu skill", dry_run=dry_run)
    if "cursor" in hosts:
        _remove_file_if_contains(project_root / ".cursor" / "rules" / "kedu.mdc", "Kedu", result, "remove project Cursor Kedu rule", dry_run=dry_run)

    _prune_project_kedu_to_short(kedu_paths, result, dry_run=dry_run)


def parse_hosts(value: str) -> tuple[str, ...]:
    if value == "all":
        return HOSTS
    hosts = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    unknown = [host for host in hosts if host not in HOSTS]
    if unknown:
        raise ValueError(f"unknown host(s): {', '.join(unknown)}")
    return hosts or HOSTS


def _default_scan_roots() -> list[Path]:
    env_roots = os.environ.get("KEDU_PROJECT_SCAN_ROOTS")
    roots: list[Path] = []
    if env_roots:
        roots.extend(Path(part).expanduser() for part in env_roots.split(os.pathsep) if part)

    home = Path.home()
    roots.extend(
        [
            Path.cwd(),
            home / "Development",
            home / "Projects",
            home / "work",
            home / "workspace",
        ]
    )

    volumes = Path("/Volumes")
    if volumes.exists():
        for volume in volumes.iterdir():
            if not volume.is_dir():
                continue
            for name in ("Development", "Projects", "work", "workspace", "workplace"):
                roots.append(volume / name)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        if not resolved.exists() or not resolved.is_dir():
            continue
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            deduped.append(resolved)
    return deduped


def _looks_like_kedu_project(path: Path) -> bool:
    return any(
        candidate.exists()
        for candidate in (
            path / ".kedu" / "config.json",
            path / ".kedu" / "short.jsonl",
            path / ".kiro" / "agents" / "kedu.json",
            path / ".kiro" / "steering" / "kedu.md",
            path / ".kiro" / "skills" / "kedu" / "SKILL.md",
            path / ".claude" / "skills" / "kedu" / "SKILL.md",
            path / ".claude" / "skills" / "kedu-log" / "SKILL.md",
            path / ".claude" / "skills" / "kedu-search" / "SKILL.md",
            path / ".agents" / "skills" / "kedu" / "SKILL.md",
            path / ".cursor" / "rules" / "kedu.mdc",
        )
    )


def discover_project_roots(scan_roots: list[str | Path] | None = None, *, max_depth: int = DEFAULT_SCAN_DEPTH) -> list[Path]:
    roots = [Path(root).expanduser() for root in scan_roots] if scan_roots else _default_scan_roots()
    discovered: list[Path] = []
    seen: set[str] = set()

    for root in roots:
        try:
            resolved_root = root.resolve()
        except OSError:
            continue
        if not resolved_root.exists() or not resolved_root.is_dir():
            continue
        root_depth = len(resolved_root.parts)
        for current, dirnames, _filenames in os.walk(resolved_root):
            current_path = Path(current)
            depth = len(current_path.parts) - root_depth
            dirnames[:] = [name for name in dirnames if name not in SCAN_SKIP_DIRS]
            if _looks_like_kedu_project(current_path):
                key = str(current_path.resolve())
                if key not in seen:
                    seen.add(key)
                    discovered.append(current_path.resolve())
                dirnames[:] = [name for name in dirnames if name not in {".kedu", ".claude", ".kiro", ".cursor"}]
            if depth >= max_depth:
                dirnames[:] = []
    return discovered


def cleanup(
    *,
    user: bool,
    project_root: str | Path | None,
    project: str | None = None,
    hosts: tuple[str, ...] = HOSTS,
    bin_dir: str | Path | None = None,
    install_root: str | Path | None = None,
    scan_projects: bool = False,
    scan_roots: list[str | Path] | None = None,
    scan_depth: int = DEFAULT_SCAN_DEPTH,
    dry_run: bool = True,
) -> CleanupResult:
    result = CleanupResult(dry_run=dry_run)
    kedu_home = paths_mod.kedu_home()
    resolved_bin_dir = Path(bin_dir or os.environ.get("KEDU_BIN_DIR", "~/.local/bin")).expanduser()
    resolved_install_root = Path(install_root or os.environ.get("KEDU_INSTALL_ROOT", kedu_home / "kedu")).expanduser()

    if user:
        cleanup_user_install(
            result,
            bin_dir=resolved_bin_dir,
            install_root=resolved_install_root,
            kedu_home=kedu_home,
            hosts=hosts,
            dry_run=dry_run,
        )

    project_roots: list[Path] = []
    if project_root is not None:
        project_roots.append(Path(project_root).expanduser().resolve())
    if scan_projects:
        project_roots.extend(discover_project_roots(scan_roots, max_depth=scan_depth))

    seen_roots: set[str] = set()
    for resolved_project_root in project_roots:
        key = str(resolved_project_root)
        if key in seen_roots:
            continue
        seen_roots.add(key)
        cleanup_project_install(
            result,
            project_root=resolved_project_root,
            project=project,
            hosts=hosts,
            dry_run=dry_run,
        )

    if not user and project_root is None and not scan_projects:
        result.warnings.append("nothing selected; use uninstall without scope flags or pass --user-only/--project-only")

    return result
