from __future__ import annotations

import json

import pytest

from scripts import init_cmd


def _clear_agent_envs(monkeypatch) -> None:
    for var in ("KEDU_AGENT", "CLAUDE_SESSION_ID", "CLAUDECODE", "KIRO_SESSION_ID", "KIRO_HOME", "CODEX_SESSION_ID", "CODEX_HOME", "CURSOR_SESSION_ID", "CURSOR_HOME"):
        monkeypatch.delenv(var, raising=False)


def test_global_init_requires_agent_when_not_detected(kedu_env, monkeypatch):
    _clear_agent_envs(monkeypatch)
    with pytest.raises(init_cmd.AgentDetectionError, match="could not detect"):
        init_cmd.init_kedu(mode="global", cwd=kedu_env["project"])


def test_global_init_for_detected_codex(kedu_env, monkeypatch, tmp_path):
    _clear_agent_envs(monkeypatch)
    agent_home = tmp_path / "agent-home"
    monkeypatch.setenv("CODEX_HOME", str(kedu_env["project"] / "codex-home"))
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    result = init_cmd.init_kedu(mode="global", cwd=kedu_env["project"])
    assert result.mode == "global"
    assert result.host == "codex"
    assert not (kedu_env["project"] / "AGENTS.md").exists()
    assert (agent_home / ".agents" / "skills" / "kedu" / "SKILL.md").exists()
    assert (kedu_env["home"] / "agents" / "codex-kedu-skill.md").exists()


def test_global_init_for_claude_installs_skills_and_memory_override(kedu_env, monkeypatch):
    claude_home = kedu_env["project"] / "claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    result = init_cmd.init_kedu(mode="global", agent="claude", cwd=kedu_env["project"])
    assert result.mode == "global"
    assert result.host == "claude"
    assert (claude_home / "CLAUDE.md").exists()
    skill = claude_home / "skills" / "kedu" / "SKILL.md"
    assert skill.exists()
    assert "/kedu log" in skill.read_text(encoding="utf-8")
    claude_text = (claude_home / "CLAUDE.md").read_text(encoding="utf-8")
    assert "memory log" in claude_text
    assert "obsolete" in claude_text
    assert "====kedu start ====" in claude_text
    assert not (claude_home / "settings.json").exists()


def test_local_init_for_detected_codex(kedu_env, monkeypatch):
    _clear_agent_envs(monkeypatch)
    monkeypatch.setenv("CODEX_HOME", str(kedu_env["project"] / "codex-home"))
    result = init_cmd.init_kedu(mode="local", cwd=kedu_env["project"])
    project_kedu = kedu_env["project"] / ".kedu"
    config = json.loads((project_kedu / "config.json").read_text(encoding="utf-8"))
    assert result.mode == "local"
    assert result.host == "codex"
    assert config["project"] == "repo"
    assert config["kedu_home"] == str(kedu_env["home"])
    assert config["enabled_agents"] == ["codex"]
    assert (project_kedu / "short.jsonl").exists()
    assert (project_kedu / "STATE.md").exists()
    assert not (kedu_env["project"] / "AGENTS.md").exists()
    skill = kedu_env["project"] / ".agents" / "skills" / "kedu" / "SKILL.md"
    assert skill.exists()
    assert "kedu" in skill.read_text(encoding="utf-8")


def test_local_init_for_claude_installs_project_skills(kedu_env):
    result = init_cmd.init_kedu(mode="local", agent="claude", cwd=kedu_env["project"])
    assert result.host == "claude"
    assert (kedu_env["project"] / "CLAUDE.md").exists()
    assert not (kedu_env["project"] / ".claude" / "settings.local.json").exists()
    skill = kedu_env["project"] / ".claude" / "skills" / "kedu" / "SKILL.md"
    assert skill.exists()
    assert "/kedu search" in skill.read_text(encoding="utf-8")
    text = (kedu_env["project"] / "CLAUDE.md").read_text(encoding="utf-8")
    assert "====kedu start ====" in text
    assert "====kedu stop line:" in text


def test_local_init_refreshes_existing_kedu_block(kedu_env):
    target = kedu_env["project"] / "CLAUDE.md"
    target.write_text(
        "Before\n\n<!-- kedu:start -->\nold Kedu block\n<!-- kedu:end -->\n\nAfter\n",
        encoding="utf-8",
    )

    init_cmd.init_kedu(mode="local", agent="claude", cwd=kedu_env["project"])

    text = target.read_text(encoding="utf-8")
    assert "old Kedu block" not in text
    assert "Legacy naming note" in text
    assert "<!-- kedu:start -->" not in text
    assert "====kedu start ====" in text
    assert "Before" in text
    assert "After" in text


def test_local_init_preserves_multiple_enabled_agents(kedu_env):
    init_cmd.init_kedu(mode="local", agent="codex", cwd=kedu_env["project"])
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=kedu_env["project"])
    config = json.loads((kedu_env["project"] / ".kedu" / "config.json").read_text(encoding="utf-8"))
    assert config["enabled_agents"] == ["codex", "kiro"]
    assert config["default_agent"] == "codex"


def test_local_init_supports_agent_override(kedu_env):
    result = init_cmd.init_kedu(mode="local", agent="kiro", cwd=kedu_env["project"])
    assert result.host == "kiro"
    steering = kedu_env["project"] / ".kiro" / "steering" / "kedu.md"
    assert steering.exists()
    steering_text = steering.read_text(encoding="utf-8")
    assert "not a Kiro skill" in steering_text
    assert "Do not search a skill registry" in steering_text
    assert "spec = intended plan; Kedu = historical evidence" in steering_text
    assert "obsolete" in steering_text
    assert "does not use automatic Kedu hooks" in steering_text
    hook = kedu_env["project"] / ".kiro" / "hooks" / "kedu-clean-exit.kiro.hook"
    assert not hook.exists()
    cli_agent = kedu_env["project"] / ".kiro" / "agents" / "kedu.json"
    assert cli_agent.exists()
    agent_config = json.loads(cli_agent.read_text(encoding="utf-8"))
    assert agent_config["name"] == "kedu"
    assert "Kedu Session Records" in agent_config["prompt"]
    assert "memory log" in agent_config["prompt"]
    assert "does not use automatic Kedu hooks" in agent_config["prompt"]
    assert "agentStop" not in agent_config["prompt"]
    assert "scripts/kedu.py" in agent_config["prompt"]
    assert (kedu_env["project"] / ".kiro" / "prompts" / "kedu-agent-prompt.md").exists()


def test_local_init_adds_git_info_exclude(kedu_env):
    git_info = kedu_env["project"] / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text("# local excludes\n", encoding="utf-8")
    init_cmd.init_kedu(mode="local", agent="cursor", cwd=kedu_env["project"])
    assert ".kedu/" in (git_info / "exclude").read_text(encoding="utf-8")
