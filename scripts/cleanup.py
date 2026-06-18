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
        QIJU_BLOCK_END,
        QIJU_BLOCK_START,
        find_line_marked_block,
    )
    from . import paths as paths_mod, util
except ImportError:  # pragma: no cover
    from block_format import (  # type: ignore
        CLAUDE_BLOCK_START,
        CLAUDE_BLOCK_STOP_PREFIX,
        QIJU_BLOCK_END,
        QIJU_BLOCK_START,
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
    ".qiju",
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
        result.preserved.append({"path": str(path), "reason": "file does not look Qiju-owned"})
        return
    _remove_file(path, result, reason, dry_run=dry_run)


def _remove_qiju_block(path: Path, result: CleanupResult, *, dry_run: bool) -> None:
    if not path.exists() or not path.is_file():
        return
    content = path.read_text(encoding="utf-8")
    line_marked = find_line_marked_block(content)
    if line_marked:
        start, end = line_marked
    else:
        start = content.find(QIJU_BLOCK_START)
        end = content.find(QIJU_BLOCK_END)
        if start != -1 and end != -1 and end >= start:
            end += len(QIJU_BLOCK_END)
        else:
            start = end = -1
    if start == -1 or end == -1 or end < start:
        result.preserved.append({"path": str(path), "reason": "no Qiju block found"})
        return
    updated = (content[:start].rstrip() + "\n\n" + content[end:].lstrip()).strip() + "\n"
    _add_action(result, "remove_qiju_block", path, "remove generated Qiju instruction block", dry_run=dry_run)
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
    config_path = project_root / ".qiju" / "config.json"
    if not config_path.exists():
        return None
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict) and isinstance(loaded.get("project"), str):
        return loaded["project"]
    return None


def _prune_project_qiju_to_short(qiju_paths: paths_mod.QijuPaths, result: CleanupResult, *, dry_run: bool) -> None:
    if not qiju_paths.project_qiju_dir.exists():
        result.preserved.append({"path": str(qiju_paths.project_qiju_dir), "reason": "project .qiju directory does not exist"})
        return

    # SAFETY GUARD: if the project's .qiju directory resolves to — or is an ancestor of —
    # the global Qiju store, refuse to touch it. Otherwise (e.g. running uninstall from
    # $HOME, where project_root/.qiju == ~/.qiju) we would rm -rf the global long/archive
    # records. Memory is NEVER removed by uninstall.
    home_store = paths_mod.qiju_home()
    if _contains_path(qiju_paths.project_qiju_dir, home_store):
        result.preserved.append({
            "path": str(qiju_paths.project_qiju_dir),
            "reason": "project .qiju resolves to the global Qiju store; refusing to remove memory (long/archive)",
        })
        return

    short_count = _entry_count(qiju_paths.short_jsonl)
    long_count = _entry_count(qiju_paths.long_jsonl)
    if long_count:
        result.preserved.append({"path": str(qiju_paths.long_jsonl), "reason": f"global long records are never removed by uninstall: long={long_count}"})

    if short_count:
        for child in qiju_paths.project_qiju_dir.iterdir():
            if child.name == "short.jsonl":
                continue
            reason = "remove generated project .qiju metadata; preserve short records"
            if child.is_dir():
                _remove_dir(child, result, reason, dry_run=dry_run)
            else:
                _remove_file(child, result, reason, dry_run=dry_run)
        result.preserved.append({"path": str(qiju_paths.short_jsonl), "reason": f"preserve project short records: short={short_count}"})
        return

    _remove_dir(
        qiju_paths.project_qiju_dir,
        result,
        "remove project .qiju metadata; no local short records (global long/archive preserved)",
        dry_run=dry_run,
    )


def cleanup_user_install(
    result: CleanupResult,
    *,
    bin_dir: Path,
    install_root: Path,
    qiju_home: Path,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    shim = bin_dir / "qiju"
    if shim.exists():
        try:
            content = shim.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = ""
        if str(install_root) in content or ".venv/bin/qiju" in content:
            _remove_file(shim, result, "remove Qiju CLI shim", dry_run=dry_run)
        else:
            result.preserved.append({"path": str(shim), "reason": "qiju shim does not look owned by this install"})

    if install_root.resolve() == qiju_home.resolve() or _contains_path(install_root, qiju_home):
        result.preserved.append(
            {
                "path": str(install_root),
                "reason": "install root overlaps Qiju home; refusing to remove possible records",
            }
        )
    else:
        _remove_dir(install_root, result, "remove installed Qiju engine", dry_run=dry_run)
    for child in ("adapters", "agents", "logs"):
        _remove_dir(qiju_home / child, result, "remove installed Qiju support templates", dry_run=dry_run)

    # The query_log feature was removed; a query_log.jsonl left by a prior install is now
    # orphaned non-memory data. Remove it (redaction_log.jsonl is audit data — preserved).
    _remove_file(qiju_home / "query_log.jsonl", result, "remove legacy Qiju query log", dry_run=dry_run)

    # The lock file is an empty fcntl lock created at runtime by writes — operational, not memory.
    _remove_file(qiju_home / ".qiju.lock", result, "remove Qiju runtime lock", dry_run=dry_run)

    launch_agents = Path.home() / "Library" / "LaunchAgents"
    if launch_agents.exists():
        for plist in launch_agents.glob("*.qiju*.plist"):
            _remove_file_if_contains(plist, "qiju", result, "remove Qiju launchd maintenance job", dry_run=dry_run)

    if "codex" in hosts:
        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        agent_home = Path(os.environ.get("AGENT_HOME", "~")).expanduser()
        _remove_qiju_block(codex_home / "AGENTS.md", result, dry_run=dry_run)
        _remove_dir(codex_home / "skills" / "qiju", result, "remove legacy global Codex Qiju skill", dry_run=dry_run)
        _remove_dir(codex_home / "skills" / "qiju-log", result, "remove legacy global Codex Qiju log skill", dry_run=dry_run)
        _remove_dir(codex_home / "skills" / "qiju-search", result, "remove legacy global Codex Qiju search skill", dry_run=dry_run)
        _remove_dir(codex_home / "skills" / "qiju-review", result, "remove legacy global Codex Qiju review skill", dry_run=dry_run)
        _remove_dir(agent_home / ".agents" / "skills" / "qiju", result, "remove legacy global Codex Qiju skill", dry_run=dry_run)
        _remove_dir(agent_home / ".agents" / "skills" / "qiju-log", result, "remove global Codex Qiju log skill", dry_run=dry_run)
        _remove_dir(agent_home / ".agents" / "skills" / "qiju-search", result, "remove global Codex Qiju search skill", dry_run=dry_run)
        _remove_dir(agent_home / ".agents" / "skills" / "qiju-review", result, "remove global Codex Qiju review skill", dry_run=dry_run)
    if "claude" in hosts:
        claude_home = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
        _remove_qiju_block(claude_home / "CLAUDE.md", result, dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "qiju", result, "remove Claude Qiju skill", dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "qiju-log", result, "remove Claude Qiju log skill", dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "qiju-search", result, "remove Claude Qiju search skill", dry_run=dry_run)
        _remove_dir(claude_home / "skills" / "qiju-review", result, "remove Claude Qiju review skill", dry_run=dry_run)
    if "kiro" in hosts:
        kiro_home = Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser()
        # Init is skill-first and no longer writes Kiro steering or a saved prompt, but
        # legacy installs may still have them — purge them as the cleanup safety net.
        _remove_file_if_contains(kiro_home / "steering" / "qiju.md", "Qiju", result, "remove global Kiro Qiju steering", dry_run=dry_run)
        _remove_file_if_contains(kiro_home / "agents" / "qiju.json", "Qiju", result, "remove global Kiro Qiju CLI agent", dry_run=dry_run)
        _remove_file_if_contains(kiro_home / "prompts" / "qiju-agent-prompt.md", "Qiju", result, "remove global Kiro Qiju prompt", dry_run=dry_run)
        _remove_dir(kiro_home / "skills" / "qiju", result, "remove legacy global Kiro Qiju skill", dry_run=dry_run)
        _remove_dir(kiro_home / "skills" / "qiju-log", result, "remove global Kiro Qiju log skill", dry_run=dry_run)
        _remove_dir(kiro_home / "skills" / "qiju-search", result, "remove global Kiro Qiju search skill", dry_run=dry_run)
        _remove_dir(kiro_home / "skills" / "qiju-review", result, "remove global Kiro Qiju review skill", dry_run=dry_run)
    if "cursor" in hosts:
        cursor_home = Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser()
        _remove_file_if_contains(cursor_home / "rules" / "qiju.mdc", "Qiju", result, "remove global Cursor Qiju rule", dry_run=dry_run)
        _remove_dir(cursor_home / "skills" / "qiju", result, "remove legacy global Cursor Qiju skill", dry_run=dry_run)
        _remove_dir(cursor_home / "skills" / "qiju-log", result, "remove global Cursor Qiju log skill", dry_run=dry_run)
        _remove_dir(cursor_home / "skills" / "qiju-search", result, "remove global Cursor Qiju search skill", dry_run=dry_run)
        _remove_dir(cursor_home / "skills" / "qiju-review", result, "remove global Cursor Qiju review skill", dry_run=dry_run)

    for preserved_name in ("long", "archive", "redaction_log.jsonl"):
        path = qiju_home / preserved_name
        if path.exists():
            result.preserved.append({"path": str(path), "reason": "Qiju records/audit data are never removed by uninstall"})


def cleanup_project_install(
    result: CleanupResult,
    *,
    project_root: Path,
    project: str | None,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    resolved_project = _project_slug_from_config(project_root, project)
    qiju_paths = paths_mod.resolve_paths(project=resolved_project, cwd=project_root)

    if "codex" in hosts:
        _remove_qiju_block(project_root / "AGENTS.md", result, dry_run=dry_run)
        _remove_dir(project_root / ".agents" / "skills" / "qiju", result, "remove legacy project Codex Qiju skill", dry_run=dry_run)
        _remove_dir(project_root / ".agents" / "skills" / "qiju-log", result, "remove project Codex Qiju log skill", dry_run=dry_run)
        _remove_dir(project_root / ".agents" / "skills" / "qiju-search", result, "remove project Codex Qiju search skill", dry_run=dry_run)
        _remove_dir(project_root / ".agents" / "skills" / "qiju-review", result, "remove project Codex Qiju review skill", dry_run=dry_run)
    if "claude" in hosts:
        _remove_qiju_block(project_root / "CLAUDE.md", result, dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "qiju", result, "remove project Claude Qiju skill", dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "qiju-log", result, "remove project Claude Qiju log skill", dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "qiju-search", result, "remove project Claude Qiju search skill", dry_run=dry_run)
        _remove_dir(project_root / ".claude" / "skills" / "qiju-review", result, "remove project Claude Qiju review skill", dry_run=dry_run)
    if "kiro" in hosts:
        # Init is skill-first and no longer writes Kiro steering or a saved prompt, but
        # legacy installs may still have them — purge them as the cleanup safety net.
        _remove_file_if_contains(project_root / ".kiro" / "steering" / "qiju.md", "Qiju", result, "remove project Kiro Qiju steering", dry_run=dry_run)
        _remove_file_if_contains(project_root / ".kiro" / "agents" / "qiju.json", "Qiju", result, "remove project Kiro Qiju CLI agent", dry_run=dry_run)
        _remove_file_if_contains(project_root / ".kiro" / "prompts" / "qiju-agent-prompt.md", "Qiju", result, "remove project Kiro Qiju prompt", dry_run=dry_run)
        _remove_dir(project_root / ".kiro" / "skills" / "qiju", result, "remove legacy project Kiro Qiju skill", dry_run=dry_run)
        _remove_dir(project_root / ".kiro" / "skills" / "qiju-log", result, "remove project Kiro Qiju log skill", dry_run=dry_run)
        _remove_dir(project_root / ".kiro" / "skills" / "qiju-search", result, "remove project Kiro Qiju search skill", dry_run=dry_run)
        _remove_dir(project_root / ".kiro" / "skills" / "qiju-review", result, "remove project Kiro Qiju review skill", dry_run=dry_run)
    if "cursor" in hosts:
        _remove_file_if_contains(project_root / ".cursor" / "rules" / "qiju.mdc", "Qiju", result, "remove project Cursor Qiju rule", dry_run=dry_run)
        _remove_dir(project_root / ".cursor" / "skills" / "qiju", result, "remove legacy project Cursor Qiju skill", dry_run=dry_run)
        _remove_dir(project_root / ".cursor" / "skills" / "qiju-log", result, "remove project Cursor Qiju log skill", dry_run=dry_run)
        _remove_dir(project_root / ".cursor" / "skills" / "qiju-search", result, "remove project Cursor Qiju search skill", dry_run=dry_run)
        _remove_dir(project_root / ".cursor" / "skills" / "qiju-review", result, "remove project Cursor Qiju review skill", dry_run=dry_run)

    _prune_project_qiju_to_short(qiju_paths, result, dry_run=dry_run)


def parse_hosts(value: str) -> tuple[str, ...]:
    if value == "all":
        return HOSTS
    hosts = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    unknown = [host for host in hosts if host not in HOSTS]
    if unknown:
        raise ValueError(f"unknown host(s): {', '.join(unknown)}")
    return hosts or HOSTS


def _default_scan_roots() -> list[Path]:
    env_roots = os.environ.get("QIJU_PROJECT_SCAN_ROOTS")
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


def _looks_like_qiju_project(path: Path) -> bool:
    return any(
        candidate.exists()
        for candidate in (
            path / ".qiju" / "config.json",
            path / ".qiju" / "short.jsonl",
            path / ".kiro" / "agents" / "qiju.json",
            path / ".kiro" / "steering" / "qiju.md",
            path / ".kiro" / "skills" / "qiju" / "SKILL.md",
            path / ".kiro" / "skills" / "qiju-log" / "SKILL.md",
            path / ".kiro" / "skills" / "qiju-search" / "SKILL.md",
            path / ".kiro" / "skills" / "qiju-review" / "SKILL.md",
            path / ".claude" / "skills" / "qiju" / "SKILL.md",
            path / ".claude" / "skills" / "qiju-log" / "SKILL.md",
            path / ".claude" / "skills" / "qiju-search" / "SKILL.md",
            path / ".claude" / "skills" / "qiju-review" / "SKILL.md",
            path / ".agents" / "skills" / "qiju" / "SKILL.md",
            path / ".agents" / "skills" / "qiju-log" / "SKILL.md",
            path / ".agents" / "skills" / "qiju-search" / "SKILL.md",
            path / ".agents" / "skills" / "qiju-review" / "SKILL.md",
            path / ".cursor" / "skills" / "qiju" / "SKILL.md",
            path / ".cursor" / "skills" / "qiju-log" / "SKILL.md",
            path / ".cursor" / "skills" / "qiju-search" / "SKILL.md",
            path / ".cursor" / "skills" / "qiju-review" / "SKILL.md",
            path / ".cursor" / "rules" / "qiju.mdc",
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
            if _looks_like_qiju_project(current_path):
                key = str(current_path.resolve())
                if key not in seen:
                    seen.add(key)
                    discovered.append(current_path.resolve())
                dirnames[:] = [name for name in dirnames if name not in {".qiju", ".claude", ".kiro", ".cursor"}]
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
    qiju_home = paths_mod.qiju_home()
    resolved_bin_dir = Path(bin_dir or os.environ.get("QIJU_BIN_DIR", "~/.local/bin")).expanduser()
    resolved_install_root = Path(install_root or os.environ.get("QIJU_INSTALL_ROOT", qiju_home / "qiju")).expanduser()

    if user:
        cleanup_user_install(
            result,
            bin_dir=resolved_bin_dir,
            install_root=resolved_install_root,
            qiju_home=qiju_home,
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
