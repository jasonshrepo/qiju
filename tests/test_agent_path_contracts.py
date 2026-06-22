"""Agent path contracts — the executable form of the RELEASE.md Smoke Matrix.

Each test asserts that `qiju init` writes its files to the EXACT path the real agent
reads, with a comment citing the vendor doc that defines that path. These are the tests
that would have caught the Codex skill-path bug (init wrote ~/.codex/skills, but Codex
reads ~/.agents/skills).

Rule: a contract test asserts the external requirement, not the code's current behavior.
When a vendor changes a path, update the citation and the assertion together.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from qiju import capture, cleanup, init_cmd, paths


def _repo_root() -> Path:
    """Resolve the development/ repo root from init_cmd's location, cwd-independent."""
    # init_cmd.py lives at <repo>/scripts/init_cmd.py
    return Path(init_cmd.__file__).resolve().parents[1]


# --------------------------------------------------------------------------------------
# Claude Code
# Contract: project CLAUDE.md + skills under .claude/skills/<name>/SKILL.md; user-level
# under ~/.claude/. https://docs.claude.com/en/docs/claude-code/skills
# --------------------------------------------------------------------------------------

def _assert_skill_frontmatter(path: Path, *, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} must open with YAML frontmatter"
    frontmatter = text.split("---", 2)[1]
    assert f"name: {name}" in frontmatter
    assert "description:" in frontmatter
    return text


def test_contract_claude_local(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="claude", cwd=project)
    skills = project / ".claude" / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    # Skill-first: no CLAUDE.md block written, no unified /qiju skill.
    assert not (project / "CLAUDE.md").exists()
    assert not (skills / "qiju" / "SKILL.md").exists()


def test_contract_claude_global(qiju_env, monkeypatch, tmp_path):
    claude_home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    init_cmd.init_qiju(mode="global", agent="claude", cwd=qiju_env["project"])
    skills = claude_home / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert not (claude_home / "CLAUDE.md").exists()
    assert not (skills / "qiju" / "SKILL.md").exists()


# --------------------------------------------------------------------------------------
# Codex
# Contract: repo-scope skills at <repo>/.agents/skills/<name>/SKILL.md, user-scope at
# ~/.agents/skills/<name>/SKILL.md. SKILL.md must carry name+description frontmatter.
# https://developers.openai.com/codex/skills
# Regression guards: Codex does NOT read ~/.codex/skills, and Qiju no longer writes
# AGENTS.md (it duplicated Kiro steering and is not the Codex-native mechanism).
# --------------------------------------------------------------------------------------

def test_contract_codex_local(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    skills = project / ".agents" / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert not (project / "AGENTS.md").exists()
    assert not (skills / "qiju" / "SKILL.md").exists()


def test_contract_codex_global(qiju_env, monkeypatch, tmp_path):
    agent_home = tmp_path / "agent-home"
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    init_cmd.init_qiju(mode="global", agent="codex", cwd=qiju_env["project"])
    skills = agent_home / ".agents" / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    # Regression guards for the original bug:
    assert not (codex_home / "skills" / "qiju").exists()
    assert not (codex_home / "skills" / "qiju-log").exists()
    assert not (codex_home / "skills" / "qiju-search").exists()
    assert not (codex_home / "skills" / "qiju-review").exists()
    assert not (codex_home / "AGENTS.md").exists()


def test_contract_codex_skill_has_required_frontmatter(qiju_env):
    # https://developers.openai.com/codex/skills: "The SKILL.md file must include name
    # and description." Both skills must carry it, and the log skill must resolve the
    # {agent} token to the codex identity.
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    log_text = _assert_skill_frontmatter(
        project / ".agents" / "skills" / "qiju-log" / "SKILL.md", name="qiju-log"
    )
    assert "--agent codex" in log_text
    assert "{agent}" not in log_text
    _assert_skill_frontmatter(
        project / ".agents" / "skills" / "qiju-search" / "SKILL.md", name="qiju-search"
    )
    _assert_skill_frontmatter(
        project / ".agents" / "skills" / "qiju-review" / "SKILL.md", name="qiju-review"
    )


# --------------------------------------------------------------------------------------
# Kiro
# Contract: provider-neutral Agent Skills only. Project skills live at
# .kiro/skills/<name>/SKILL.md and user skills under ~/.kiro/skills/<name>/SKILL.md.
# Qiju does not ship or generate a provider-specific .kiro/agents/qiju.json config,
# and the old .kiro/prompts/ saved prompt is retired.
# --------------------------------------------------------------------------------------

def test_contract_kiro_local(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="kiro", cwd=project)
    skills = project / ".kiro" / "skills"
    log_text = _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    assert "--agent kiro" in log_text
    assert "{agent}" not in log_text
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert not (skills / "qiju" / "SKILL.md").exists()
    assert not (project / ".kiro" / "agents" / "qiju.json").exists()
    assert not (project / ".kiro" / "steering" / "qiju.md").exists()
    assert not (project / ".kiro" / "prompts" / "qiju-agent-prompt.md").exists()


def test_contract_kiro_global(qiju_env, monkeypatch, tmp_path):
    kiro_home = tmp_path / "kiro-home"
    monkeypatch.setenv("KIRO_HOME", str(kiro_home))
    init_cmd.init_qiju(mode="global", agent="kiro", cwd=qiju_env["project"])
    skills = kiro_home / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert not (skills / "qiju" / "SKILL.md").exists()
    assert not (kiro_home / "agents" / "qiju.json").exists()
    assert not (kiro_home / "steering" / "qiju.md").exists()
    assert not (kiro_home / "prompts" / "qiju-agent-prompt.md").exists()


# --------------------------------------------------------------------------------------
# Cursor
# Contract: project skills at .cursor/skills/<name>/SKILL.md and user skills at
# ~/.cursor/skills/<name>/SKILL.md.
# https://cursor.com/docs/skills
# --------------------------------------------------------------------------------------

def test_contract_cursor_local(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="cursor", cwd=project)
    skills = project / ".cursor" / "skills"
    log_text = _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert "--agent cursor" in log_text
    assert not (project / ".cursor" / "rules" / "qiju.mdc").exists()


def test_contract_cursor_global(qiju_env, monkeypatch, tmp_path):
    cursor_home = tmp_path / "cursor-home"
    monkeypatch.setenv("CURSOR_HOME", str(cursor_home))
    init_cmd.init_qiju(mode="global", agent="cursor", cwd=qiju_env["project"])
    skills = cursor_home / "skills"
    _assert_skill_frontmatter(skills / "qiju-log" / "SKILL.md", name="qiju-log")
    _assert_skill_frontmatter(skills / "qiju-search" / "SKILL.md", name="qiju-search")
    _assert_skill_frontmatter(skills / "qiju-review" / "SKILL.md", name="qiju-review")
    assert not (cursor_home / "rules" / "qiju.mdc").exists()


# --------------------------------------------------------------------------------------
# Uninstall round-trip
# Contract: what `qiju init` creates, `qiju uninstall` removes — except records.
# (RELEASE.md §E/§F.) These assert the project-scope agent file created by init is gone
# after uninstall, and that durable records survive.
# --------------------------------------------------------------------------------------

def test_contract_codex_uninstall_removes_skill(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    skills = project / ".agents" / "skills"
    assert (skills / "qiju-log" / "SKILL.md").exists()
    assert (skills / "qiju-search" / "SKILL.md").exists()
    assert (skills / "qiju-review" / "SKILL.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)
    assert not (skills / "qiju-log").exists()
    assert not (skills / "qiju-search").exists()
    assert not (skills / "qiju-review").exists()


def test_contract_claude_uninstall_removes_skill(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="claude", cwd=project)
    skills = project / ".claude" / "skills"
    assert (skills / "qiju-log" / "SKILL.md").exists()
    assert (skills / "qiju-search" / "SKILL.md").exists()
    assert (skills / "qiju-review" / "SKILL.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)
    assert not (skills / "qiju-log").exists()
    assert not (skills / "qiju-search").exists()
    assert not (skills / "qiju-review").exists()


def test_contract_kiro_uninstall_removes_skill_and_legacy_agent(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="kiro", cwd=project)
    cli_agent = project / ".kiro" / "agents" / "qiju.json"
    skills = project / ".kiro" / "skills"
    # Init creates only portable skills. Cleanup still purges legacy Kiro agent configs.
    assert not cli_agent.exists()
    cli_agent.parent.mkdir(parents=True)
    cli_agent.write_text('{"name":"qiju","description":"Qiju legacy agent"}\n', encoding="utf-8")
    assert (skills / "qiju-log" / "SKILL.md").exists()
    assert (skills / "qiju-search" / "SKILL.md").exists()
    assert (skills / "qiju-review" / "SKILL.md").exists()
    assert not (project / ".kiro" / "steering" / "qiju.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("kiro",), dry_run=False)
    assert not cli_agent.exists()
    assert not (skills / "qiju-log").exists()
    assert not (skills / "qiju-search").exists()
    assert not (skills / "qiju-review").exists()


def test_contract_cursor_uninstall_removes_skills_and_legacy_rule(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="cursor", cwd=project)
    skills = project / ".cursor" / "skills"
    assert (skills / "qiju-log" / "SKILL.md").exists()
    assert (skills / "qiju-search" / "SKILL.md").exists()
    assert (skills / "qiju-review" / "SKILL.md").exists()
    legacy_rule = project / ".cursor" / "rules" / "qiju.mdc"
    legacy_rule.parent.mkdir(parents=True)
    legacy_rule.write_text("Qiju legacy rule\n", encoding="utf-8")
    cleanup.cleanup(user=False, project_root=project, hosts=("cursor",), dry_run=False)
    assert not (skills / "qiju-log").exists()
    assert not (skills / "qiju-search").exists()
    assert not (skills / "qiju-review").exists()
    assert not legacy_rule.exists()


# --------------------------------------------------------------------------------------
# Session-record path resolution
# Contract: a record's identity and storage location are anchored to where `qiju init`
# ran (the `.qiju/config.json` marker), NOT to the agent's cwd at log time. Agents wander
# into subfolders; the short tier must still land at the init root. These guard the bug
# where logging from a subdir created a second project identity (slug + short.jsonl) in
# that subdir.
# --------------------------------------------------------------------------------------

def _minimal_entry(**overrides):
    entry = {"title": "t", "body_md": "b", "tags": ["x"]}
    entry.update(overrides)
    return entry


def test_log_from_subdir_resolves_to_init_root(qiju_env, monkeypatch):
    monkeypatch.delenv("QIJU_PROJECT_ROOT", raising=False)
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="claude", cwd=project)
    sub = project / "development"
    sub.mkdir()

    capture.log_entry(_minimal_entry(), source="manual", agent="claude", cwd=sub)

    # Short tier lands at the init root, not the subdir the agent wandered into.
    assert (project / ".qiju" / "short.jsonl").read_text(encoding="utf-8").strip()
    assert not (sub / ".qiju").exists()
    # Identity is the init-root slug ("repo"), so the long file matches.
    assert (qiju_env["home"] / "long" / "repo.jsonl").exists()


def test_log_without_marker_aborts(qiju_env, monkeypatch, tmp_path):
    monkeypatch.delenv("QIJU_PROJECT_ROOT", raising=False)
    bare = tmp_path / "no-init-here"
    bare.mkdir()
    # No init marker, no --project, cwd fallback -> refuse to mint a new identity.
    with pytest.raises(SystemExit):
        capture.log_entry(_minimal_entry(), source="manual", agent="claude", cwd=bare)


def test_env_var_overrides_cwd(qiju_env, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("QIJU_PROJECT_ROOT", str(qiju_env["project"]))
    resolved = paths.resolve_paths(cwd=elsewhere)
    assert resolved.root_origin == "env"
    assert resolved.project_root == qiju_env["project"].resolve()


def test_slug_stable_after_root_rename(qiju_env, monkeypatch):
    monkeypatch.delenv("QIJU_PROJECT_ROOT", raising=False)
    project = qiju_env["project"]
    # Init pins a canonical slug into the marker, independent of the directory name.
    init_cmd.init_qiju(mode="local", agent="claude", project="canonical-name", cwd=project)
    sub = project / "development"
    sub.mkdir()
    resolved = paths.resolve_paths(cwd=sub)
    assert resolved.project == "canonical-name"
    assert resolved.root_origin == "marker"


def test_contract_uninstall_preserves_records(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    # A project short record and a global long record must both survive uninstall.
    short = project / ".qiju" / "short.jsonl"
    short.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    long_file = qiju_env["home"] / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert short.exists()
    assert long_file.exists()


# --------------------------------------------------------------------------------------
# Shipped templates vs generated behavior
# Contract: Qiju ships only provider-neutral skills/<name>/SKILL.md skill packages.
# Provider-specific Kiro agent config files are not part of the active package.
# --------------------------------------------------------------------------------------

def test_release_template_has_no_kiro_agent_config():
    repo = _repo_root()
    template_path = repo / "agents" / "kiro" / "agents" / "qiju.json"
    assert not template_path.exists()


def test_release_templates_retired_paths_absent():
    repo = _repo_root()
    assert not (repo / "agents" / "kiro" / "prompts" / "qiju-agent-prompt.md").exists()
    assert not (repo / "agents" / "kiro" / "steering" / "qiju.md").exists()
