from __future__ import annotations

import json

import pytest

from qiju import init_cmd


def _clear_agent_envs(monkeypatch) -> None:
    for var in ("QIJU_AGENT", "CLAUDE_SESSION_ID", "CLAUDECODE", "KIRO_SESSION_ID", "KIRO_HOME", "CODEX_SESSION_ID", "CODEX_HOME", "CURSOR_SESSION_ID", "CURSOR_HOME"):
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


def test_cli_init_multi_host_emits_list(qiju_env, monkeypatch, capsys):
    from qiju import cli as qiju

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(qiju_env["project"])
    assert qiju.main(["init", "--host", "claude,codex", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list)
    assert [result["host"] for result in out] == ["claude", "codex"]


def test_cli_init_single_host_still_emits_object(qiju_env, monkeypatch, capsys):
    from qiju import cli as qiju

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(qiju_env["project"])
    assert qiju.main(["init", "--host", "claude", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, dict)
    assert out["host"] == "claude"


def test_cli_init_default_output_is_human_readable(qiju_env, monkeypatch, capsys):
    from qiju import cli as qiju

    _clear_agent_envs(monkeypatch)
    monkeypatch.chdir(qiju_env["project"])
    assert qiju.main(["init", "--host", "claude,codex"]) == 0
    out = capsys.readouterr().out
    # Default is a human-readable summary, not JSON.
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert "qiju init (local)" in out
    assert "[claude]" in out and "[codex]" in out
    assert "Summary: 2 hosts wired (claude, codex)" in out


def test_global_init_requires_agent_when_not_detected(qiju_env, monkeypatch):
    _clear_agent_envs(monkeypatch)
    with pytest.raises(init_cmd.AgentDetectionError, match="could not detect"):
        init_cmd.init_qiju(mode="global", cwd=qiju_env["project"])


def test_global_init_for_detected_codex(qiju_env, monkeypatch, tmp_path):
    _clear_agent_envs(monkeypatch)
    agent_home = tmp_path / "agent-home"
    monkeypatch.setenv("CODEX_HOME", str(qiju_env["project"] / "codex-home"))
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    result = init_cmd.init_qiju(mode="global", cwd=qiju_env["project"])
    assert result.mode == "global"
    assert result.host == "codex"
    assert not (qiju_env["project"] / "AGENTS.md").exists()
    assert (agent_home / ".agents" / "skills" / "qiju-log" / "SKILL.md").exists()
    assert (agent_home / ".agents" / "skills" / "qiju-search" / "SKILL.md").exists()
    assert (agent_home / ".agents" / "skills" / "qiju-review" / "SKILL.md").exists()
    assert (qiju_env["home"] / "agents" / "codex-qiju-log-skill.md").exists()
    assert (qiju_env["home"] / "agents" / "codex-qiju-search-skill.md").exists()
    assert (qiju_env["home"] / "agents" / "codex-qiju-review-skill.md").exists()


def test_global_init_for_claude_installs_skills_no_claude_block(qiju_env, monkeypatch):
    claude_home = qiju_env["project"] / "claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    result = init_cmd.init_qiju(mode="global", agent="claude", cwd=qiju_env["project"])
    assert result.mode == "global"
    assert result.host == "claude"
    # Skill-first: no CLAUDE.md block is written on init.
    assert not (claude_home / "CLAUDE.md").exists()
    log_skill = claude_home / "skills" / "qiju-log" / "SKILL.md"
    search_skill = claude_home / "skills" / "qiju-search" / "SKILL.md"
    review_skill = claude_home / "skills" / "qiju-review" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert review_skill.exists()
    assert "name: qiju-log" in log_skill.read_text(encoding="utf-8")
    assert "name: qiju-search" in search_skill.read_text(encoding="utf-8")
    assert "name: qiju-review" in review_skill.read_text(encoding="utf-8")
    assert not (claude_home / "skills" / "qiju" / "SKILL.md").exists()
    assert not (claude_home / "settings.json").exists()


def test_local_init_for_detected_codex(qiju_env, monkeypatch):
    _clear_agent_envs(monkeypatch)
    monkeypatch.setenv("CODEX_HOME", str(qiju_env["project"] / "codex-home"))
    result = init_cmd.init_qiju(mode="local", cwd=qiju_env["project"])
    project_qiju = qiju_env["project"] / ".qiju"
    config = json.loads((project_qiju / "config.json").read_text(encoding="utf-8"))
    assert result.mode == "local"
    assert result.host == "codex"
    assert config["project"] == "repo"
    assert config["qiju_home"] == str(qiju_env["home"])
    assert config["enabled_agents"] == ["codex"]
    assert (project_qiju / "short.jsonl").exists()
    assert not (qiju_env["project"] / "AGENTS.md").exists()
    log_skill = qiju_env["project"] / ".agents" / "skills" / "qiju-log" / "SKILL.md"
    search_skill = qiju_env["project"] / ".agents" / "skills" / "qiju-search" / "SKILL.md"
    review_skill = qiju_env["project"] / ".agents" / "skills" / "qiju-review" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert review_skill.exists()
    assert "--agent codex" in log_skill.read_text(encoding="utf-8")
    assert "7-Day Qiju Review" in review_skill.read_text(encoding="utf-8")


def test_local_init_for_claude_installs_project_skills(qiju_env):
    result = init_cmd.init_qiju(mode="local", agent="claude", cwd=qiju_env["project"])
    assert result.host == "claude"
    # Skill-first: init writes NO CLAUDE.md block.
    assert not (qiju_env["project"] / "CLAUDE.md").exists()
    assert not (qiju_env["project"] / ".claude" / "settings.local.json").exists()
    log_skill = qiju_env["project"] / ".claude" / "skills" / "qiju-log" / "SKILL.md"
    search_skill = qiju_env["project"] / ".claude" / "skills" / "qiju-search" / "SKILL.md"
    review_skill = qiju_env["project"] / ".claude" / "skills" / "qiju-review" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert review_skill.exists()
    assert "--agent claude" in log_skill.read_text(encoding="utf-8")
    search_text = search_skill.read_text(encoding="utf-8")
    assert "--format actions" in search_text
    assert "name: qiju-review" in review_skill.read_text(encoding="utf-8")
    assert not (qiju_env["project"] / ".claude" / "skills" / "qiju" / "SKILL.md").exists()


def test_local_init_preserves_multiple_enabled_agents(qiju_env):
    init_cmd.init_qiju(mode="local", agent="codex", cwd=qiju_env["project"])
    init_cmd.init_qiju(mode="local", agent="kiro", cwd=qiju_env["project"])
    config = json.loads((qiju_env["project"] / ".qiju" / "config.json").read_text(encoding="utf-8"))
    assert config["enabled_agents"] == ["codex", "kiro"]
    assert config["default_agent"] == "codex"


def test_local_init_supports_agent_override(qiju_env):
    result = init_cmd.init_qiju(mode="local", agent="kiro", cwd=qiju_env["project"])
    assert result.host == "kiro"
    # Kiro init is provider-neutral: skills only, no steering, saved prompt, or agent config.
    assert not (qiju_env["project"] / ".kiro" / "steering" / "qiju.md").exists()
    assert not (qiju_env["project"] / ".kiro" / "prompts" / "qiju-agent-prompt.md").exists()
    hook = qiju_env["project"] / ".kiro" / "hooks" / "qiju-clean-exit.kiro.hook"
    assert not hook.exists()
    cli_agent = qiju_env["project"] / ".kiro" / "agents" / "qiju.json"
    assert not cli_agent.exists()
    log_skill = qiju_env["project"] / ".kiro" / "skills" / "qiju-log" / "SKILL.md"
    search_skill = qiju_env["project"] / ".kiro" / "skills" / "qiju-search" / "SKILL.md"
    review_skill = qiju_env["project"] / ".kiro" / "skills" / "qiju-review" / "SKILL.md"
    assert log_skill.exists()
    assert search_skill.exists()
    assert review_skill.exists()
    assert "name: qiju-log" in log_skill.read_text(encoding="utf-8")
    assert "name: qiju-search" in search_skill.read_text(encoding="utf-8")
    assert "name: qiju-review" in review_skill.read_text(encoding="utf-8")
    assert "--agent kiro" in log_skill.read_text(encoding="utf-8")
    assert not (qiju_env["project"] / ".kiro" / "skills" / "qiju" / "SKILL.md").exists()


def test_local_init_adds_git_info_exclude(qiju_env):
    git_info = qiju_env["project"] / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text("# local excludes\n", encoding="utf-8")
    init_cmd.init_qiju(mode="local", agent="cursor", cwd=qiju_env["project"])
    assert ".qiju/" in (git_info / "exclude").read_text(encoding="utf-8")
