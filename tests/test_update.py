from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from qiju import register, update_cmd


def _make_project(path: Path, slug: str, agents: list[str]) -> Path:
    """Create a minimal qiju-enabled project directory."""
    path.mkdir(parents=True, exist_ok=True)
    qiju_dir = path / ".qiju"
    qiju_dir.mkdir()
    config = {
        "schema_version": 1,
        "project": slug,
        "enabled_agents": agents,
    }
    (qiju_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return path


def _write_skill_files(project: Path, agent: str) -> None:
    """Pre-populate skill files as if init had been run."""
    skill_dirs = {
        "claude": project / ".claude" / "skills",
        "kiro": project / ".kiro" / "skills",
        "codex": project / ".agents" / "skills",
        "cursor": project / ".cursor" / "skills",
    }
    skills_dir = skill_dirs[agent]
    for skill_name in ("qiju-log", "qiju-search", "qiju-review"):
        skill_file = skills_dir / skill_name / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(f"old content for {skill_name}", encoding="utf-8")


# --- read_enabled_agents ---

def test_read_enabled_agents_returns_list(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["claude", "kiro"])
    assert update_cmd.read_enabled_agents(project) == ["claude", "kiro"]


def test_read_enabled_agents_returns_empty_on_missing_file(qiju_env, tmp_path):
    assert update_cmd.read_enabled_agents(tmp_path / "nope") == []


def test_read_enabled_agents_returns_empty_on_malformed_config(qiju_env, tmp_path):
    project = tmp_path / "bad"
    project.mkdir()
    (project / ".qiju").mkdir()
    (project / ".qiju" / "config.json").write_text("not json", encoding="utf-8")
    assert update_cmd.read_enabled_agents(project) == []


# --- update_project_install ---

def test_update_project_install_dry_run_writes_nothing(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["claude"])
    _write_skill_files(project, "claude")

    result = update_cmd.UpdateResult(dry_run=True)
    update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=True)

    skill = project / ".claude" / "skills" / "qiju-log" / "SKILL.md"
    assert skill.read_text(encoding="utf-8") == "old content for qiju-log"
    assert len(result.projects) == 1
    assert result.projects[0]["status"] == "would update"
    assert "claude" in result.projects[0]["hosts"]


def test_update_project_install_overwrites_skill_files(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["claude"])
    _write_skill_files(project, "claude")

    result = update_cmd.UpdateResult(dry_run=False)
    update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=False)

    skill = project / ".claude" / "skills" / "qiju-log" / "SKILL.md"
    content = skill.read_text(encoding="utf-8")
    assert "old content" not in content
    assert "qiju-log" in content.lower() or "qiju" in content
    assert result.projects[0]["status"] == "updated"


def test_update_project_install_skips_when_no_matching_hosts(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["kiro"])

    result = update_cmd.UpdateResult(dry_run=False)
    update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=False)

    assert result.projects[0]["status"] == "skipped"
    assert result.projects[0]["hosts"] == []


def test_update_project_install_unchanged_when_files_current(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["claude"])

    # First update writes the skill files fresh.
    result = update_cmd.UpdateResult(dry_run=False)
    update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=False)
    assert result.projects[0]["status"] == "updated"

    # Second update finds identical content -> unchanged, no writes needed.
    result2 = update_cmd.UpdateResult(dry_run=False)
    update_cmd.update_project_install(result2, project_root=project, hosts=("claude",), dry_run=False)
    assert result2.projects[0]["status"] == "unchanged"


def test_update_project_install_missing_when_config_absent(qiju_env, tmp_path):
    # Directory exists but is not a qiju project (no .qiju/config.json).
    project = tmp_path / "gone"
    project.mkdir()

    result = update_cmd.UpdateResult(dry_run=False)
    update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=False)

    assert result.projects[0]["status"] == "missing"
    assert result.projects[0]["hosts"] == []


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX chmod-based write-failure injection has no effect on Windows",
)
def test_update_project_install_failed_on_write_error(qiju_env, tmp_path):
    project = _make_project(tmp_path / "proj", "proj", ["claude"])
    # Pre-create the skill directory as a read-only target so writes raise.
    skills_dir = project / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    os.chmod(skills_dir, 0o500)
    try:
        result = update_cmd.UpdateResult(dry_run=False)
        update_cmd.update_project_install(result, project_root=project, hosts=("claude",), dry_run=False)
    finally:
        os.chmod(skills_dir, 0o700)

    assert result.projects[0]["status"] == "failed"
    assert "error" in result.projects[0]
    assert result.warnings  # failure surfaced as a warning


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX chmod-based write-failure injection has no effect on Windows",
)
def test_update_continues_after_one_project_fails(qiju_env, tmp_path, monkeypatch):
    # Two registered projects; one has a read-only skill dir so it fails.
    good = _make_project(tmp_path / "good", "good", ["claude"])
    bad = _make_project(tmp_path / "bad", "bad", ["claude"])
    register.register_project(good, "good")
    register.register_project(bad, "bad")

    bad_skills = bad / ".claude" / "skills"
    bad_skills.mkdir(parents=True)
    os.chmod(bad_skills, 0o500)
    try:
        result = update_cmd.update(project_root=tmp_path / "nowhere", dry_run=False)
    finally:
        os.chmod(bad_skills, 0o700)

    statuses = {p["slug"]: p["status"] for p in result.projects}
    assert statuses.get("good") == "updated"
    assert statuses.get("bad") == "failed"


# --- update() ---

def test_update_updates_registered_projects(qiju_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p1 = _make_project(tmp_path / "p1", "p1", ["claude"])
    p2 = _make_project(tmp_path / "p2", "p2", ["kiro"])
    _write_skill_files(p1, "claude")
    _write_skill_files(p2, "kiro")
    register.register_project(p1, "p1")
    register.register_project(p2, "p2")

    result = update_cmd.update(project_root=tmp_path, hosts=("claude", "kiro"), dry_run=False)

    statuses = {p["slug"]: p["status"] for p in result.projects}
    assert statuses.get("p1") == "updated"
    assert statuses.get("p2") == "updated"


def test_update_auto_registers_current_project(qiju_env, tmp_path, monkeypatch):
    current = _make_project(tmp_path / "current", "current", ["claude"])
    monkeypatch.chdir(current)

    update_cmd.update(project_root=current, dry_run=False)

    projects_map = register.read_registry()
    assert str(current.resolve()) in projects_map


def test_update_dry_run_does_not_prune_registry(qiju_env, tmp_path, monkeypatch):
    # A stale registry entry (project deleted) must not be pruned during dry_run.
    gone = tmp_path / "gone"
    gone.mkdir()
    register.register_project(gone, "gone")
    gone.rmdir()
    monkeypatch.chdir(tmp_path)

    update_cmd.update(project_root=tmp_path, dry_run=True)

    projects_map = register.read_registry()
    assert str(gone.resolve()) in projects_map


def test_update_dry_run_does_not_register_current_project(qiju_env, tmp_path, monkeypatch):
    current = _make_project(tmp_path / "current", "current", ["claude"])
    monkeypatch.chdir(current)

    update_cmd.update(project_root=current, dry_run=True)

    projects_map = register.read_registry()
    assert str(current.resolve()) not in projects_map


def test_update_scan_projects_dry_run_does_not_backfill_registry(qiju_env, tmp_path, monkeypatch):
    _make_project(tmp_path / "discovered", "discovered", ["claude"])
    monkeypatch.chdir(tmp_path)

    update_cmd.update(
        project_root=tmp_path,
        scan_projects=True,
        scan_roots=[str(tmp_path)],
        dry_run=True,
    )

    projects_map = register.read_registry()
    assert projects_map == {}


def test_update_empty_registry_no_scan_returns_recovery_warning(qiju_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = update_cmd.update(project_root=tmp_path, dry_run=False)

    assert len(result.warnings) == 1
    assert "--scan-projects" in result.warnings[0]
    assert len(result.projects) == 0


def test_update_empty_registry_no_scan_writes_nothing(qiju_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a_project = _make_project(tmp_path / "proj", "proj", ["claude"])
    _write_skill_files(a_project, "claude")
    # Do NOT register the project

    result = update_cmd.update(project_root=tmp_path, dry_run=False)

    assert result.warnings
    skill = a_project / ".claude" / "skills" / "qiju-log" / "SKILL.md"
    assert skill.read_text(encoding="utf-8") == "old content for qiju-log"


def test_update_scan_projects_discovers_and_backfills(qiju_env, tmp_path, monkeypatch):
    project = _make_project(tmp_path / "discovered", "discovered", ["claude"])
    monkeypatch.chdir(tmp_path)

    result = update_cmd.update(
        project_root=tmp_path,
        scan_projects=True,
        scan_roots=[str(tmp_path)],
        dry_run=False,
    )

    projects_map = register.read_registry()
    assert str(project.resolve()) in projects_map
    statuses = {p["slug"]: p["status"] for p in result.projects}
    assert statuses.get("discovered") == "updated"


def test_update_host_filter_updates_only_matching(qiju_env, tmp_path, monkeypatch):
    project = _make_project(tmp_path / "proj", "proj", ["claude", "kiro"])
    _write_skill_files(project, "claude")
    _write_skill_files(project, "kiro")
    register.register_project(project, "proj")
    monkeypatch.chdir(tmp_path)

    result = update_cmd.update(project_root=tmp_path, hosts=("claude",), dry_run=False)

    proj_entry = next(p for p in result.projects if p["slug"] == "proj")
    assert proj_entry["hosts"] == ["claude"]


def test_update_does_not_touch_records_or_config(qiju_env, tmp_path, monkeypatch):
    project = _make_project(tmp_path / "proj", "proj", ["claude"])
    config_path = project / ".qiju" / "config.json"
    original_config = config_path.read_text(encoding="utf-8")
    short_jsonl = project / ".qiju" / "short.jsonl"
    short_jsonl.write_text('{"id":"r1"}\n', encoding="utf-8")
    register.register_project(project, "proj")
    monkeypatch.chdir(tmp_path)

    update_cmd.update(project_root=tmp_path, hosts=("claude",), dry_run=False)

    assert config_path.read_text(encoding="utf-8") == original_config
    assert short_jsonl.read_text(encoding="utf-8") == '{"id":"r1"}\n'


# --- global hosts ---

def test_update_global_hosts_dry_run(qiju_env, tmp_path, monkeypatch):
    claude_home = tmp_path / "claude-home"
    (claude_home / "skills" / "qiju-log").mkdir(parents=True)
    (claude_home / "skills" / "qiju-log" / "SKILL.md").write_text("old", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))

    result = update_cmd.UpdateResult(dry_run=True)
    update_cmd.update_global_hosts(result, hosts=("claude",), dry_run=True)

    assert len(result.global_hosts) == 1
    assert result.global_hosts[0]["status"] == "would update"
    assert (claude_home / "skills" / "qiju-log" / "SKILL.md").read_text(encoding="utf-8") == "old"


def test_update_global_hosts_skips_uninitialized_host(qiju_env, tmp_path, monkeypatch):
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir(parents=True)
    # No skills dir at all
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))

    result = update_cmd.UpdateResult(dry_run=True)
    update_cmd.update_global_hosts(result, hosts=("claude",), dry_run=True)

    assert result.global_hosts == []


# --- CLI ---

def test_cli_update_dry_run(qiju_env, tmp_path, monkeypatch, capsys):
    from qiju import cli as qiju_cli
    project = _make_project(tmp_path / "proj", "proj", ["claude"])
    register.register_project(project, "proj")
    monkeypatch.chdir(tmp_path)

    rc = qiju_cli.main(["update", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out


def test_cli_update_json(qiju_env, tmp_path, monkeypatch, capsys):
    from qiju import cli as qiju_cli
    monkeypatch.chdir(tmp_path)

    rc = qiju_cli.main(["update", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "projects" in data
    assert "warnings" in data
