"""Agent path contracts — the executable form of the RELEASE.md Smoke Matrix.

Each test asserts that `kedu init` writes its files to the EXACT path the real agent
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

from scripts import capture, cleanup, init_cmd, paths


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


def test_contract_claude_local(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="claude", cwd=project)
    skills = project / ".claude" / "skills"
    _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    # Skill-first: no CLAUDE.md block written, no unified /kedu skill.
    assert not (project / "CLAUDE.md").exists()
    assert not (skills / "kedu" / "SKILL.md").exists()


def test_contract_claude_global(kedu_env, monkeypatch, tmp_path):
    claude_home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    init_cmd.init_kedu(mode="global", agent="claude", cwd=kedu_env["project"])
    skills = claude_home / "skills"
    _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    assert not (claude_home / "CLAUDE.md").exists()
    assert not (skills / "kedu" / "SKILL.md").exists()


# --------------------------------------------------------------------------------------
# Codex
# Contract: repo-scope skills at <repo>/.agents/skills/<name>/SKILL.md, user-scope at
# ~/.agents/skills/<name>/SKILL.md. SKILL.md must carry name+description frontmatter.
# https://developers.openai.com/codex/skills
# Regression guards: Codex does NOT read ~/.codex/skills, and Kedu no longer writes
# AGENTS.md (it duplicated Kiro steering and is not the Codex-native mechanism).
# --------------------------------------------------------------------------------------

def test_contract_codex_local(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    skills = project / ".agents" / "skills"
    _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    assert not (project / "AGENTS.md").exists()
    assert not (skills / "kedu" / "SKILL.md").exists()


def test_contract_codex_global(kedu_env, monkeypatch, tmp_path):
    agent_home = tmp_path / "agent-home"
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    init_cmd.init_kedu(mode="global", agent="codex", cwd=kedu_env["project"])
    skills = agent_home / ".agents" / "skills"
    _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    # Regression guards for the original bug:
    assert not (codex_home / "skills" / "kedu").exists()
    assert not (codex_home / "AGENTS.md").exists()


def test_contract_codex_skill_has_required_frontmatter(kedu_env):
    # https://developers.openai.com/codex/skills: "The SKILL.md file must include name
    # and description." Both skills must carry it, and the log skill must resolve the
    # {agent} token to the codex identity.
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    log_text = _assert_skill_frontmatter(
        project / ".agents" / "skills" / "kedu-log" / "SKILL.md", name="kedu-log"
    )
    assert "--agent codex" in log_text
    assert "{agent}" not in log_text
    _assert_skill_frontmatter(
        project / ".agents" / "skills" / "kedu-search" / "SKILL.md", name="kedu-search"
    )


# --------------------------------------------------------------------------------------
# Kiro
# Contract: SKILL-FIRST. CLI agent at .kiro/agents/<name>.json and Agent Skill at
# .kiro/skills/<name>/SKILL.md (the `/kedu` slash command, used by both IDE and CLI).
# The CLI agent registers the skill through its `resources` field. User-level under
# ~/.kiro/. NO steering file is written (always-on steering made Kiro IDE unreliable at
# writing records), and the old .kiro/prompts/ saved prompt is retired.
# --------------------------------------------------------------------------------------

def test_contract_kiro_local(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=project)
    assert (project / ".kiro" / "agents" / "kedu.json").exists()
    skills = project / ".kiro" / "skills"
    log_text = _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    assert "--agent kiro" in log_text
    assert "{agent}" not in log_text
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    assert not (skills / "kedu" / "SKILL.md").exists()
    assert not (project / ".kiro" / "steering" / "kedu.md").exists()
    assert not (project / ".kiro" / "prompts" / "kedu-agent-prompt.md").exists()


def test_contract_kiro_global(kedu_env, monkeypatch, tmp_path):
    kiro_home = tmp_path / "kiro-home"
    monkeypatch.setenv("KIRO_HOME", str(kiro_home))
    init_cmd.init_kedu(mode="global", agent="kiro", cwd=kedu_env["project"])
    assert (kiro_home / "agents" / "kedu.json").exists()
    skills = kiro_home / "skills"
    _assert_skill_frontmatter(skills / "kedu-log" / "SKILL.md", name="kedu-log")
    _assert_skill_frontmatter(skills / "kedu-search" / "SKILL.md", name="kedu-search")
    assert not (skills / "kedu" / "SKILL.md").exists()
    assert not (kiro_home / "steering" / "kedu.md").exists()
    assert not (kiro_home / "prompts" / "kedu-agent-prompt.md").exists()


# --------------------------------------------------------------------------------------
# Cursor
# Contract: rules at .cursor/rules/<name>.mdc (project) and ~/.cursor/rules/ (user).
# https://docs.cursor.com/context/rules
# --------------------------------------------------------------------------------------

def test_contract_cursor_local(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="cursor", cwd=project)
    rule = project / ".cursor" / "rules" / "kedu.mdc"
    assert rule.exists()
    # Cursor has no slash-command skills: one rule carries BOTH bodies.
    text = rule.read_text(encoding="utf-8")
    assert "alwaysApply: false" in text
    assert "Save a Kedu Session Record" in text  # log body
    assert "Search Kedu Session Records" in text  # search body
    assert "--agent cursor" in text


def test_contract_cursor_global(kedu_env, monkeypatch, tmp_path):
    cursor_home = tmp_path / "cursor-home"
    monkeypatch.setenv("CURSOR_HOME", str(cursor_home))
    init_cmd.init_kedu(mode="global", agent="cursor", cwd=kedu_env["project"])
    assert (cursor_home / "rules" / "kedu.mdc").exists()


# --------------------------------------------------------------------------------------
# Uninstall round-trip
# Contract: what `kedu init` creates, `kedu uninstall` removes — except records.
# (RELEASE.md §E/§F.) These assert the project-scope agent file created by init is gone
# after uninstall, and that durable records survive.
# --------------------------------------------------------------------------------------

def test_contract_codex_uninstall_removes_skill(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    skills = project / ".agents" / "skills"
    assert (skills / "kedu-log" / "SKILL.md").exists()
    assert (skills / "kedu-search" / "SKILL.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)
    assert not (skills / "kedu-log").exists()
    assert not (skills / "kedu-search").exists()


def test_contract_claude_uninstall_removes_skill(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="claude", cwd=project)
    skills = project / ".claude" / "skills"
    assert (skills / "kedu-log" / "SKILL.md").exists()
    assert (skills / "kedu-search" / "SKILL.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)
    assert not (skills / "kedu-log").exists()
    assert not (skills / "kedu-search").exists()


def test_contract_kiro_uninstall_removes_skill_and_agent(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=project)
    cli_agent = project / ".kiro" / "agents" / "kedu.json"
    skills = project / ".kiro" / "skills"
    # Skill-first init creates the CLI agent and the two skills, not a steering file.
    assert cli_agent.exists()
    assert (skills / "kedu-log" / "SKILL.md").exists()
    assert (skills / "kedu-search" / "SKILL.md").exists()
    assert not (project / ".kiro" / "steering" / "kedu.md").exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("kiro",), dry_run=False)
    assert not cli_agent.exists()
    assert not (skills / "kedu-log").exists()
    assert not (skills / "kedu-search").exists()


def test_contract_cursor_uninstall_removes_rule(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="cursor", cwd=project)
    rule = project / ".cursor" / "rules" / "kedu.mdc"
    assert rule.exists()
    cleanup.cleanup(user=False, project_root=project, hosts=("cursor",), dry_run=False)
    assert not rule.exists()


# --------------------------------------------------------------------------------------
# Session-record path resolution
# Contract: a record's identity and storage location are anchored to where `kedu init`
# ran (the `.kedu/config.json` marker), NOT to the agent's cwd at log time. Agents wander
# into subfolders; the short tier must still land at the init root. These guard the bug
# where logging from a subdir created a second project identity (slug + short.jsonl) in
# that subdir.
# --------------------------------------------------------------------------------------

def _minimal_entry(**overrides):
    entry = {"title": "t", "body_md": "b", "tags": ["x"]}
    entry.update(overrides)
    return entry


def test_log_from_subdir_resolves_to_init_root(kedu_env, monkeypatch):
    monkeypatch.delenv("KEDU_PROJECT_ROOT", raising=False)
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="claude", cwd=project)
    sub = project / "development"
    sub.mkdir()

    capture.log_entry(_minimal_entry(), source="manual", agent="claude", cwd=sub)

    # Short tier lands at the init root, not the subdir the agent wandered into.
    assert (project / ".kedu" / "short.jsonl").read_text(encoding="utf-8").strip()
    assert not (sub / ".kedu").exists()
    # Identity is the init-root slug ("repo"), so the long file matches.
    assert (kedu_env["home"] / "long" / "repo.jsonl").exists()


def test_log_without_marker_aborts(kedu_env, monkeypatch, tmp_path):
    monkeypatch.delenv("KEDU_PROJECT_ROOT", raising=False)
    bare = tmp_path / "no-init-here"
    bare.mkdir()
    # No init marker, no --project, cwd fallback -> refuse to mint a new identity.
    with pytest.raises(SystemExit):
        capture.log_entry(_minimal_entry(), source="manual", agent="claude", cwd=bare)


def test_env_var_overrides_cwd(kedu_env, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("KEDU_PROJECT_ROOT", str(kedu_env["project"]))
    resolved = paths.resolve_paths(cwd=elsewhere)
    assert resolved.root_origin == "env"
    assert resolved.project_root == kedu_env["project"].resolve()


def test_slug_stable_after_root_rename(kedu_env, monkeypatch):
    monkeypatch.delenv("KEDU_PROJECT_ROOT", raising=False)
    project = kedu_env["project"]
    # Init pins a canonical slug into the marker, independent of the directory name.
    init_cmd.init_kedu(mode="local", agent="claude", project="canonical-name", cwd=project)
    sub = project / "development"
    sub.mkdir()
    resolved = paths.resolve_paths(cwd=sub)
    assert resolved.project == "canonical-name"
    assert resolved.root_origin == "marker"


def test_contract_uninstall_preserves_records(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    # A project short record and a global long record must both survive uninstall.
    short = project / ".kedu" / "short.jsonl"
    short.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    long_file = kedu_env["home"] / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert short.exists()
    assert long_file.exists()


# --------------------------------------------------------------------------------------
# Shipped templates vs generated behavior
# Contract: the checked-in support templates under agents/kiro/ must not contradict what
# `kedu init` generates. The Kiro integration is skill-first, so the shipped agent config
# must register the skill via `resources` and must not claim "not a Kiro skill" or point
# at the retired prompts path. Retired template files must be absent from the repo.
# --------------------------------------------------------------------------------------

def test_release_template_kiro_agent_matches_generated():
    repo = _repo_root()
    template_path = repo / "agents" / "kiro" / "agents" / "kedu.json"
    assert template_path.exists()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    generated = json.loads(init_cmd._kiro_agent_config())

    # Static fields must match the generator.
    assert template["resources"] == generated["resources"]
    assert "skill://.kiro/skills/*/SKILL.md" in template["resources"]
    assert template["name"] == generated["name"]
    assert template["tools"] == generated["tools"]

    # Skill-first prompt: no stale "not a Kiro skill" claim, must reference both skills,
    # must not point at the retired saved-prompt path.
    prompt = template["prompt"]
    assert "not a Kiro skill" not in prompt
    assert ".kiro/skills/kedu-log/SKILL.md" in prompt
    assert ".kiro/skills/kedu-search/SKILL.md" in prompt
    assert "kedu-agent-prompt" not in prompt


def test_release_templates_retired_paths_absent():
    repo = _repo_root()
    assert not (repo / "agents" / "kiro" / "prompts" / "kedu-agent-prompt.md").exists()
    assert not (repo / "agents" / "kiro" / "steering" / "kedu.md").exists()
