from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from . import paths as paths_mod, register as register_mod
    from .init_cmd import _write_file, _qiju_log_skill, _qiju_search_skill, _qiju_review_skill, init_global_agent
    from .cleanup import discover_project_roots, DEFAULT_SCAN_DEPTH, HOSTS
except ImportError:  # pragma: no cover
    import paths as paths_mod  # type: ignore
    import register as register_mod  # type: ignore
    from init_cmd import _write_file, _qiju_log_skill, _qiju_search_skill, _qiju_review_skill, init_global_agent  # type: ignore
    from cleanup import discover_project_roots, DEFAULT_SCAN_DEPTH, HOSTS  # type: ignore


_RECOVERY_MSG = (
    "No registered Qiju projects found (the project registry under ~/.qiju/ is missing or empty).\n"
    "Rebuild it by scanning your project roots:\n"
    "\n"
    "    qiju update --scan-projects                 # scan standard roots\n"
    "    qiju update --scan-projects --scan-root ~/code   # or specify roots\n"
    "\n"
    "Newly created projects (qiju init) register themselves automatically."
)

_AGENT_SKILL_DIRS: dict[str, str] = {
    "claude": ".claude/skills",
    "kiro": ".kiro/skills",
    "codex": ".agents/skills",
    "cursor": ".cursor/skills",
}


def read_enabled_agents(project_root: str | Path) -> list[str]:
    config_path = Path(project_root) / ".qiju" / "config.json"
    if not config_path.exists():
        return []
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, dict):
        return []
    agents = loaded.get("enabled_agents", [])
    if not isinstance(agents, list):
        return []
    return [a for a in agents if isinstance(a, str)]


def _read_project_slug(project_root: str | Path) -> str:
    config_path = Path(project_root) / ".qiju" / "config.json"
    if not config_path.exists():
        return Path(project_root).name
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Path(project_root).name
    if isinstance(loaded, dict) and isinstance(loaded.get("project"), str):
        return loaded["project"]
    return Path(project_root).name


@dataclass
class UpdateResult:
    dry_run: bool
    projects: list[dict] = field(default_factory=list)
    global_hosts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "projects": self.projects,
            "global_hosts": self.global_hosts,
            "warnings": self.warnings,
            "notes": self.notes,
        }


def update_project_install(
    result: UpdateResult,
    *,
    project_root: Path,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    slug = _read_project_slug(project_root)
    config_path = Path(project_root) / ".qiju" / "config.json"
    if not config_path.exists():
        result.projects.append({"path": str(project_root), "slug": slug, "hosts": [], "status": "missing"})
        return
    agents = read_enabled_agents(project_root)
    active = [a for a in agents if a in hosts]
    if not active:
        result.projects.append({"path": str(project_root), "slug": slug, "hosts": [], "status": "skipped"})
        return
    if dry_run:
        result.projects.append({"path": str(project_root), "slug": slug, "hosts": active, "status": "would update"})
        return
    try:
        changed = False
        for agent in active:
            skills_dir = project_root / _AGENT_SKILL_DIRS[agent]
            if _write_file(skills_dir / "qiju-log" / "SKILL.md", _qiju_log_skill(agent)):
                changed = True
            if _write_file(skills_dir / "qiju-search" / "SKILL.md", _qiju_search_skill()):
                changed = True
            if _write_file(skills_dir / "qiju-review" / "SKILL.md", _qiju_review_skill()):
                changed = True
    except OSError as exc:
        result.projects.append({
            "path": str(project_root),
            "slug": slug,
            "hosts": active,
            "status": "failed",
            "error": str(exc),
        })
        result.warnings.append(f"failed to update {project_root}: {exc}")
        return
    result.projects.append({
        "path": str(project_root),
        "slug": slug,
        "hosts": active,
        "status": "updated" if changed else "unchanged",
    })


def _global_skill_root(agent: str) -> Path | None:
    if agent == "claude":
        return Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser() / "skills"
    elif agent == "kiro":
        return Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser() / "skills"
    elif agent == "codex":
        agent_home = Path(os.environ.get("AGENT_HOME", "~")).expanduser()
        return agent_home / ".agents" / "skills"
    elif agent == "cursor":
        return Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser() / "skills"
    return None


def update_global_hosts(
    result: UpdateResult,
    *,
    hosts: tuple[str, ...],
    dry_run: bool,
) -> None:
    for host in hosts:
        skills_root = _global_skill_root(host)
        if skills_root is None:
            continue
        if not any((skills_root / skill).exists() for skill in ("qiju-log", "qiju-search", "qiju-review")):
            continue
        if not dry_run:
            init_global_agent(host)
        result.global_hosts.append({"host": host, "status": "would update" if dry_run else "updated"})


def update(
    *,
    project_root: str | Path = ".",
    hosts: tuple[str, ...] = HOSTS,
    scan_projects: bool = False,
    scan_roots: list[str | Path] | None = None,
    scan_depth: int = DEFAULT_SCAN_DEPTH,
    dry_run: bool = False,
) -> UpdateResult:
    result = UpdateResult(dry_run=dry_run)

    registered, pruned = register_mod.registered_roots(prune=not dry_run)
    for note in pruned:
        result.notes.append(f"pruned stale registry entry: {note}")

    resolved_current = Path(project_root).expanduser().resolve()
    current_config = resolved_current / ".qiju" / "config.json"
    extra_roots: list[Path] = []
    if current_config.exists():
        extra_roots.append(resolved_current)
        slug = _read_project_slug(resolved_current)
        if not dry_run:
            register_mod.register_project(resolved_current, slug)

    scanned_roots: list[Path] = []
    if scan_projects:
        scanned_roots = discover_project_roots(scan_roots, max_depth=scan_depth)
        for root in scanned_roots:
            slug = _read_project_slug(root)
            if not dry_run:
                register_mod.register_project(root, slug)

    all_roots = list(registered) + extra_roots + scanned_roots

    seen: set[str] = set()
    deduped: list[Path] = []
    for root in all_roots:
        resolved = root.resolve()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            deduped.append(resolved)

    if not deduped and not scan_projects:
        result.warnings.append(_RECOVERY_MSG)
        return result

    for root in deduped:
        update_project_install(result, project_root=root, hosts=hosts, dry_run=dry_run)

    update_global_hosts(result, hosts=hosts, dry_run=dry_run)

    return result
