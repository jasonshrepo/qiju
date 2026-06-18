from __future__ import annotations

import json
import os
from datetime import datetime

from scripts import cleanup, init_cmd


def test_user_cleanup_removes_installation_but_preserves_records(qiju_env, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))

    home = qiju_env["home"]
    install_root = home / "qiju"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    install_root.mkdir(parents=True)
    (install_root / "README.md").write_text("installed copy", encoding="utf-8")
    for name in ("adapters", "agents", "logs"):
        directory = home / name
        directory.mkdir(parents=True)
        (directory / "file.txt").write_text("template", encoding="utf-8")
    long_dir = home / "long"
    archive_dir = home / "archive" / "project=repo" / "month=2026-01"
    long_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    (long_dir / "repo.jsonl").write_text('{"id":"1"}\n', encoding="utf-8")
    (archive_dir / "entries.parquet").write_text("archive", encoding="utf-8")
    (home / "query_log.jsonl").write_text('{"query":"x"}\n', encoding="utf-8")
    (home / "redaction_log.jsonl").write_text('{"event":"x"}\n', encoding="utf-8")
    (bin_dir / "qiju").write_text(f'exec "{install_root}/.venv/bin/qiju" "$@"\n', encoding="utf-8")

    result = cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=("codex",),
        bin_dir=bin_dir,
        install_root=install_root,
        dry_run=False,
    )

    assert not (bin_dir / "qiju").exists()
    assert not install_root.exists()
    assert not (home / "adapters").exists()
    assert not (home / "agents").exists()
    assert not (home / "logs").exists()
    assert (long_dir / "repo.jsonl").exists()
    assert (archive_dir / "entries.parquet").exists()
    # The query_log feature was removed: a pre-existing legacy query log is now deleted,
    # while the redaction-log audit trail is still preserved.
    assert not (home / "query_log.jsonl").exists()
    assert (home / "redaction_log.jsonl").exists()
    assert any("legacy Qiju query log" in action.reason for action in result.actions)
    assert any("never removed" in item["reason"] for item in result.preserved)


def test_global_cleanup_removes_codex_and_kiro_skills(qiju_env, tmp_path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    codex_home = tmp_path / "codex-home"
    kiro_home = tmp_path / "kiro-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("KIRO_HOME", str(kiro_home))
    init_cmd.init_qiju(mode="global", agent="codex", cwd=qiju_env["project"])
    init_cmd.init_qiju(mode="global", agent="kiro", cwd=qiju_env["project"])
    for skill_name in ("qiju-log", "qiju-search", "qiju-review"):
        legacy_skill = codex_home / "skills" / skill_name
        legacy_skill.mkdir(parents=True)
        (legacy_skill / "SKILL.md").write_text(f"name: {skill_name}\n", encoding="utf-8")
    assert (agent_home / ".agents" / "skills" / "qiju-log" / "SKILL.md").exists()
    assert (agent_home / ".agents" / "skills" / "qiju-review" / "SKILL.md").exists()
    assert (codex_home / "skills" / "qiju-review" / "SKILL.md").exists()
    assert (kiro_home / "skills" / "qiju-search" / "SKILL.md").exists()
    assert (kiro_home / "skills" / "qiju-review" / "SKILL.md").exists()

    cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=("codex", "kiro"),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        dry_run=False,
    )

    assert not (agent_home / ".agents" / "skills" / "qiju-log").exists()
    assert not (agent_home / ".agents" / "skills" / "qiju-search").exists()
    assert not (agent_home / ".agents" / "skills" / "qiju-review").exists()
    assert not (codex_home / "skills" / "qiju-log").exists()
    assert not (codex_home / "skills" / "qiju-search").exists()
    assert not (codex_home / "skills" / "qiju-review").exists()
    assert not (kiro_home / "skills" / "qiju-log").exists()
    assert not (kiro_home / "skills" / "qiju-search").exists()
    assert not (kiro_home / "skills" / "qiju-review").exists()


def test_user_cleanup_refuses_install_root_that_overlaps_record_store(qiju_env, tmp_path):
    home = qiju_env["home"]
    (home / "long").mkdir(parents=True)
    (home / "long" / "repo.jsonl").write_text('{"id":"1"}\n', encoding="utf-8")

    result = cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=(),
        bin_dir=tmp_path / "bin",
        install_root=home,
        dry_run=False,
    )

    assert home.exists()
    assert (home / "long" / "repo.jsonl").exists()
    assert any("overlaps Qiju home" in item["reason"] for item in result.preserved)


def test_user_cleanup_removes_qiju_launch_agent(qiju_env, tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    launch_agents = home_dir / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    plist = launch_agents / "org.qiju.test.plist"
    plist.write_text("<plist><string>qiju maintain</string></plist>", encoding="utf-8")

    cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=(),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        dry_run=False,
    )

    assert not plist.exists()


def test_project_cleanup_preserves_project_qiju_when_short_records_exist(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="kiro", cwd=project)
    short = project / ".qiju" / "short.jsonl"
    short.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(user=False, project_root=project, hosts=("kiro",), dry_run=False)

    assert (project / ".qiju").exists()
    assert short.exists()
    assert not (project / ".qiju" / "config.json").exists()
    assert not (project / ".kiro" / "steering" / "qiju.md").exists()
    assert not (project / ".kiro" / "agents" / "qiju.json").exists()
    assert not (project / ".kiro" / "prompts" / "qiju-agent-prompt.md").exists()
    assert not (project / ".kiro" / "skills" / "qiju-log").exists()
    assert not (project / ".kiro" / "skills" / "qiju-search").exists()
    assert not (project / ".kiro" / "skills" / "qiju-review").exists()
    assert any("short=1" in item["reason"] for item in result.preserved)


def test_project_cleanup_removes_codex_skills(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    assert (project / ".agents" / "skills" / "qiju-log" / "SKILL.md").exists()

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".agents" / "skills" / "qiju-log").exists()
    assert not (project / ".agents" / "skills" / "qiju-search").exists()
    assert not (project / ".agents" / "skills" / "qiju-review").exists()


def test_project_cleanup_removes_project_claude_skills(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="claude", cwd=project)
    settings = project / ".claude" / "settings.local.json"
    assert not settings.exists()

    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)

    assert not (project / ".claude" / "skills" / "qiju").exists()
    assert not (project / ".claude" / "skills" / "qiju-log").exists()
    assert not (project / ".claude" / "skills" / "qiju-search").exists()
    assert not (project / ".claude" / "skills" / "qiju-review").exists()
    assert not settings.exists()


def test_project_cleanup_removes_claude_line_count_block_only(qiju_env):
    project = qiju_env["project"]
    (project / "CLAUDE.md").write_text(
        "\n".join(
            [
                "# User Claude Notes",
                "",
                "====qiju start ====",
                "## Qiju Session Records",
                "Use Qiju.",
                "====qiju stop line:2====",
                "",
                "Keep this Claude note.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)

    updated = (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Qiju Session Records" not in updated
    assert "# User Claude Notes" in updated
    assert "Keep this Claude note." in updated


def test_project_cleanup_removes_project_qiju_when_only_global_long_records_exist(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    (project / ".qiju" / "short.jsonl").write_text("", encoding="utf-8")
    long_file = qiju_env["home"] / "long" / "repo.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".qiju").exists()
    assert long_file.exists()
    assert any("long=1" in item["reason"] for item in result.preserved)


def test_project_cleanup_removes_recent_empty_project_qiju(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="cursor", cwd=project)

    result = cleanup.cleanup(user=False, project_root=project, hosts=("cursor",), dry_run=False)

    assert not (project / ".qiju").exists()
    assert any(action.action == "remove_dir" and action.path.endswith(".qiju") for action in result.actions)


def test_project_cleanup_removes_empty_project_qiju_regardless_of_age(qiju_env):
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    old_time = datetime(2025, 11, 13).timestamp()
    for path in sorted((project / ".qiju").rglob("*"), reverse=True):
        os.utime(path, (old_time, old_time))
    os.utime(project / ".qiju", (old_time, old_time))

    result = cleanup.cleanup(
        user=False,
        project_root=project,
        hosts=("codex",),
        dry_run=False,
    )

    assert not (project / ".qiju").exists()
    assert any(action.action == "remove_dir" and action.path.endswith(".qiju") for action in result.actions)


def test_project_cleanup_removes_codex_block_only(qiju_env):
    project = qiju_env["project"]
    content = "\n".join(
        [
            "# Local Instructions",
            "",
            cleanup.QIJU_BLOCK_START,
            "## Qiju Session Records",
            cleanup.QIJU_BLOCK_END,
            "",
            "Keep this project note.",
            "",
        ]
    )
    (project / "AGENTS.md").write_text(content, encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    updated = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "Qiju Session Records" not in updated
    assert "# Local Instructions" in updated
    assert "Keep this project note." in updated


def test_cleanup_scans_project_roots_and_prunes_to_short(qiju_env, tmp_path):
    scan_root = tmp_path / "scan-root"
    project_a = scan_root / "project-a"
    project_b = scan_root / "nested" / "project-b"
    project_a.mkdir(parents=True)
    project_b.mkdir(parents=True)
    init_cmd.init_qiju(mode="local", agent="kiro", cwd=project_a)
    init_cmd.init_qiju(mode="local", agent="claude", cwd=project_b)
    (project_a / ".qiju" / "short.jsonl").write_text(json.dumps({"id": "a:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(
        user=False,
        project_root=None,
        hosts=("claude", "kiro"),
        scan_projects=True,
        scan_roots=[scan_root],
        dry_run=False,
    )

    assert (project_a / ".qiju" / "short.jsonl").exists()
    assert not (project_a / ".qiju" / "config.json").exists()
    assert not (project_a / ".kiro" / "agents" / "qiju.json").exists()
    assert not (project_b / ".qiju").exists()
    assert not (project_b / ".claude" / "skills" / "qiju").exists()
    assert not result.warnings


def test_user_cleanup_removes_runtime_lock_but_preserves_records(qiju_env, tmp_path):
    home = qiju_env["home"]
    home.mkdir(parents=True, exist_ok=True)
    lock = home / ".qiju.lock"
    lock.write_text("", encoding="utf-8")
    long_dir = home / "long"
    long_dir.mkdir(parents=True)
    (long_dir / "repo.jsonl").write_text('{"id":"1"}\n', encoding="utf-8")
    (home / "redaction_log.jsonl").write_text('{"event":"x"}\n', encoding="utf-8")

    result = cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=(),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        dry_run=False,
    )

    assert not lock.exists()
    assert (long_dir / "repo.jsonl").exists()
    assert (home / "redaction_log.jsonl").exists()
    assert any("runtime lock" in action.reason for action in result.actions)


def test_cleanup_scans_multiple_projects_and_preserves_short(qiju_env, tmp_path):
    scan_root = tmp_path / "scan-root"
    project_a = scan_root / "project-a"
    project_b = scan_root / "project-b"
    for project in (project_a, project_b):
        skill_dir = project / ".claude" / "skills" / "qiju-log"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("Qiju skill", encoding="utf-8")
        qiju_dir = project / ".qiju"
        qiju_dir.mkdir(parents=True)
        (qiju_dir / "short.jsonl").write_text(json.dumps({"id": "x:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(
        user=False,
        project_root=None,
        scan_projects=True,
        scan_roots=[scan_root],
        dry_run=False,
    )

    assert not (project_a / ".claude" / "skills" / "qiju-log").exists()
    assert not (project_b / ".claude" / "skills" / "qiju-log").exists()
    assert (project_a / ".qiju" / "short.jsonl").exists()
    assert (project_b / ".qiju" / "short.jsonl").exists()
    assert not result.warnings


def test_project_cleanup_refuses_when_project_qiju_is_global_store(tmp_path, monkeypatch):
    # Regression: running uninstall from a dir whose ".qiju" IS the global QIJU_HOME store
    # (e.g. from $HOME) previously rm -rf'd ~/.qiju, destroying long/ and archive/.
    store = tmp_path / ".qiju"
    long_dir = store / "long"
    archive_dir = store / "archive" / "project=proj" / "month=2026-01"
    long_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    long_file = long_dir / "proj.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    (archive_dir / "entries.parquet").write_text("archive", encoding="utf-8")
    monkeypatch.setenv("QIJU_HOME", str(store))

    result = cleanup.cleanup(
        user=False,
        project_root=tmp_path,
        scan_projects=False,
        dry_run=False,
    )

    assert store.exists()
    assert long_file.exists()
    assert long_file.read_text(encoding="utf-8") == json.dumps({"id": "session-1:1"}) + "\n"
    assert archive_dir.exists()
    assert (archive_dir / "entries.parquet").exists()
    assert any("refusing to remove memory" in item["reason"] for item in result.preserved)


def test_full_uninstall_refuses_when_project_qiju_is_global_store(tmp_path, monkeypatch):
    store = tmp_path / ".qiju"
    long_dir = store / "long"
    archive_dir = store / "archive" / "project=proj" / "month=2026-01"
    long_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    long_file = long_dir / "proj.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    (archive_dir / "entries.parquet").write_text("archive", encoding="utf-8")
    monkeypatch.setenv("QIJU_HOME", str(store))

    cleanup.cleanup(
        user=True,
        project_root=tmp_path,
        hosts=(),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        scan_projects=False,
        dry_run=False,
    )

    assert long_file.exists()
    assert long_file.read_text(encoding="utf-8") == json.dumps({"id": "session-1:1"}) + "\n"
    assert archive_dir.exists()
    assert (archive_dir / "entries.parquet").exists()


def test_normal_project_cleanup_still_prunes_when_store_is_separate(qiju_env):
    # Guard must not affect genuine projects whose .qiju is unrelated to QIJU_HOME.
    project = qiju_env["project"]
    init_cmd.init_qiju(mode="local", agent="codex", cwd=project)
    (project / ".qiju" / "config.json").write_text(
        json.dumps({"project": "repo"}), encoding="utf-8"
    )
    (project / ".qiju" / "short.jsonl").write_text("", encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".qiju").exists()


def test_uninstall_cli_scans_projects_by_default():
    args = cleanup_cli_args(["uninstall"])
    assert args.scan_projects is True


def test_uninstall_cli_no_scan_projects_opt_out():
    args = cleanup_cli_args(["uninstall", "--no-scan-projects"])
    assert args.scan_projects is False


def test_cmd_uninstall_user_only_disables_scan(qiju_env, tmp_path, monkeypatch):
    from scripts import qiju as qiju_mod

    captured = {}

    def fake_cleanup(**kwargs):
        captured.update(kwargs)
        return cleanup.CleanupResult(dry_run=True)

    monkeypatch.setattr(qiju_mod.cleanup_mod, "cleanup", fake_cleanup)
    args = qiju_mod.build_parser().parse_args(["uninstall", "--user-only"])
    assert qiju_mod.cmd_uninstall(args) == 0
    assert captured["scan_projects"] is False
    assert captured["project_root"] is None


def test_uninstall_cli_supports_explicit_dry_run():
    args = cleanup_cli_args(["uninstall", "--dry-run"])
    assert args.dry_run is True
    assert args.user_only is False
    assert args.project_only is False


def test_uninstall_cli_executes_by_default():
    args = cleanup_cli_args(["uninstall"])
    assert args.dry_run is False


def test_uninstall_cli_supports_project_scan_options():
    args = cleanup_cli_args(["uninstall", "--dry-run", "--scan-root", "/tmp/projects", "--scan-depth", "4"])
    assert args.scan_root == ["/tmp/projects"]
    assert args.scan_depth == 4


def test_uninstall_prints_human_readable_output(qiju_env, tmp_path, capsys, monkeypatch):
    from scripts import qiju as qiju_mod

    monkeypatch.setenv("AGENT_HOME", str(tmp_path / "agent-home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    install_root = qiju_env["home"] / "qiju"
    install_root.mkdir(parents=True)
    (install_root / "README.md").write_text("installed copy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "qiju").write_text(f'exec "{install_root}/.venv/bin/qiju" "$@"\n', encoding="utf-8")

    args = qiju_mod.build_parser().parse_args([
        "uninstall",
        "--user-only",
        "--hosts", "codex",
        "--bin-dir", str(bin_dir),
        "--install-root", str(install_root),
    ])
    rc = qiju_mod.cmd_uninstall(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "qiju uninstall" in out
    assert "Removed:" in out
    assert "Summary:" in out
    assert "{" not in out  # no raw JSON


def test_init_cli_supports_place_alias():
    from scripts import qiju

    args = qiju.build_parser().parse_args(["init", "--host", "claude", "--place", "global"])
    assert args.place == "global"


def cleanup_cli_args(argv):
    from scripts import qiju

    return qiju.build_parser().parse_args(argv)
