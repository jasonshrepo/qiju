from __future__ import annotations

import json

import pytest

from scripts import init_cmd


def _clear_agent_envs(monkeypatch) -> None:
    for var in ("KEDU_AGENT", "CLAUDE_SESSION_ID", "CLAUDECODE", "KIRO_SESSION_ID", "KIRO_HOME", "CODEX_SESSION_ID", "CODEX_HOME", "CURSOR_SESSION_ID", "CURSOR_HOME"):
        monkeypatch.delenv(var, raising=False)


def test_parse_hosts_all_expands_to_known_agents():
    assert init_cmd.parse_hosts("all") == init_cmd.KNOWN_AGENTS


def test_parse_hosts_comma_list_canonicalizes_and_dedupes():
    assert init_cmd.parse_hosts("claude, codex ,claude-code") == ("claude", "codex")


def test_parse_hosts_empty_returns_empty_tuple_for_autodetect():
    assert init_cmd.parse_hosts(None) == ()
    assert init_cmd.parse_hosts("") == ()
    assert init_cmd.parse_hosts("  ") == ()


def test_parse_hosts_rejects_unknown_host():
    with pytest.raises(init_cmd.AgentDetectionError, match="unsupported agent: nope"):
        init_cmd.parse_hosts("claude,nope")


def test_cli_init_multi_host_emits_list(kedu_env, monkeypatch, capsys):
    from scripts import kedu

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(kedu_env["project"])
    assert kedu.main(["init", "--host", "claude,codex", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list)
    assert [result["host"] for result in out] == ["claude", "codex"]


def test_cli_init_single_host_still_emits_object(kedu_env, monkeypatch, capsys):
    from scripts import kedu

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(kedu_env["project"])
    assert kedu.main(["init", "--host", "claude", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, dict)
    assert out["host"] == "claude"


def test_cli_init_default_output_is_human_readable(kedu_env, monkeypatch, capsys):
    from scripts import kedu

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(kedu_env["project"])
    assert kedu.main(["init", "--host", "claude,codex"]) == 0
    out = capsys.readouterr().out
    # Default is a human-readable summary, not JSON.
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert "kedu init (local)" in out
    assert "[claude]" in out and "[codex]" in out
    assert "Summary: 2 hosts wired (claude, codex)" in out


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
    assert (agent_home / ".agents" / "skills" / "kedu-log" / "SKILL.md").exists()
    assert (agent_home / ".agents" / "skills" / "kedu-search" / "SKILL.md").exists()
    assert (kedu_env["home"] / "agents" / "codex-kedu-log-skill.md").exists()
    assert (kedu_env["home"] / "agents" / "codex-kedu-search-skill.md").exists()


def test_global_init_for_claude_installs_two_skills_no_claude_block(kedu_env, monkeypatch):
    claude_home = kedu_env["project"] / "claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    result = init_cmd.init_kedu(mode="global", agent="claude", cwd=kedu_env["project"])
    assert result.mode == "global"
    assert result.host == "claude"
    # Skill-first: no CLAUDE.md block is written on init.
    assert not (claude_home / "CLAUDE.md").exists()
    log_skill = claude_home / "skills" / "kedu-log" / "SKILL.md"
    search_skill = claude_home / "skills" / "kedu-search" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert "name: kedu-log" in log_skill.read_text(encoding="utf-8")
    assert "name: kedu-search" in search_skill.read_text(encoding="utf-8")
    assert not (claude_home / "skills" / "kedu" / "SKILL.md").exists()
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
    assert not (kedu_env["project"] / "AGENTS.md").exists()
    log_skill = kedu_env["project"] / ".agents" / "skills" / "kedu-log" / "SKILL.md"
    search_skill = kedu_env["project"] / ".agents" / "skills" / "kedu-search" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert "--agent codex" in log_skill.read_text(encoding="utf-8")


def test_local_init_for_claude_installs_project_skills(kedu_env):
    result = init_cmd.init_kedu(mode="local", agent="claude", cwd=kedu_env["project"])
    assert result.host == "claude"
    # Skill-first: init writes NO CLAUDE.md block.
    assert not (kedu_env["project"] / "CLAUDE.md").exists()
    assert not (kedu_env["project"] / ".claude" / "settings.local.json").exists()
    log_skill = kedu_env["project"] / ".claude" / "skills" / "kedu-log" / "SKILL.md"
    search_skill = kedu_env["project"] / ".claude" / "skills" / "kedu-search" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert "--agent claude" in log_skill.read_text(encoding="utf-8")
    search_text = search_skill.read_text(encoding="utf-8")
    assert "--format actions" in search_text
    assert not (kedu_env["project"] / ".claude" / "skills" / "kedu" / "SKILL.md").exists()


def test_local_init_preserves_multiple_enabled_agents(kedu_env):
    init_cmd.init_kedu(mode="local", agent="codex", cwd=kedu_env["project"])
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=kedu_env["project"])
    config = json.loads((kedu_env["project"] / ".kedu" / "config.json").read_text(encoding="utf-8"))
    assert config["enabled_agents"] == ["codex", "kiro"]
    assert config["default_agent"] == "codex"


def test_local_init_supports_agent_override(kedu_env):
    result = init_cmd.init_kedu(mode="local", agent="kiro", cwd=kedu_env["project"])
    assert result.host == "kiro"
    # Kiro init is skill-first: no steering file, no saved prompt.
    assert not (kedu_env["project"] / ".kiro" / "steering" / "kedu.md").exists()
    assert not (kedu_env["project"] / ".kiro" / "prompts" / "kedu-agent-prompt.md").exists()
    hook = kedu_env["project"] / ".kiro" / "hooks" / "kedu-clean-exit.kiro.hook"
    assert not hook.exists()
    cli_agent = kedu_env["project"] / ".kiro" / "agents" / "kedu.json"
    assert cli_agent.exists()
    agent_config = json.loads(cli_agent.read_text(encoding="utf-8"))
    assert agent_config["name"] == "kedu"
    assert "skill://.kiro/skills/*/SKILL.md" in agent_config["resources"]
    prompt = agent_config["prompt"]
    assert "Kedu Session Records" in prompt
    assert "memory log" in prompt
    assert "does not use automatic Kedu hooks" in prompt
    # No automatic-hook promise and no steering framing.
    assert "agentStop" not in prompt
    assert "this steering file" not in prompt
    assert "inclusion: always" not in prompt
    # Skill-first: the prompt references both Kedu skills.
    assert ".kiro/skills/kedu-log/SKILL.md" in prompt
    assert ".kiro/skills/kedu-search/SKILL.md" in prompt
    assert "scripts/kedu.py" in prompt
    log_skill = kedu_env["project"] / ".kiro" / "skills" / "kedu-log" / "SKILL.md"
    search_skill = kedu_env["project"] / ".kiro" / "skills" / "kedu-search" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert "name: kedu-log" in log_skill.read_text(encoding="utf-8")
    assert "name: kedu-search" in search_skill.read_text(encoding="utf-8")
    assert "--agent kiro" in log_skill.read_text(encoding="utf-8")
    assert not (kedu_env["project"] / ".kiro" / "skills" / "kedu" / "SKILL.md").exists()


def test_local_init_adds_git_info_exclude(kedu_env):
    git_info = kedu_env["project"] / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text("# local excludes\n", encoding="utf-8")
    init_cmd.init_kedu(mode="local", agent="cursor", cwd=kedu_env["project"])
    assert ".kedu/" in (git_info / "exclude").read_text(encoding="utf-8")
