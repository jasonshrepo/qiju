from __future__ import annotations

import json
import os
from datetime import datetime

from scripts import cleanup, init_cmd


def test_user_cleanup_removes_installation_but_preserves_records(kedu_env, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))

    home = kedu_env["home"]
    install_root = home / "kedu"
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
    (bin_dir / "kedu").write_text(f'exec "{install_root}/.venv/bin/kedu" "$@"\n', encoding="utf-8")

    result = cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=("codex",),
        bin_dir=bin_dir,
        install_root=install_root,
        dry_run=False,
    )

    assert not (bin_dir / "kedu").exists()
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
    assert any("legacy Kedu query log" in action.reason for action in result.actions)
    assert any("never removed" in item["reason"] for item in result.preserved)


def test_global_cleanup_removes_codex_and_kiro_skills(kedu_env, tmp_path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    kiro_home = tmp_path / "kiro-home"
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    monkeypatch.setenv("KIRO_HOME", str(kiro_home))
    init_cmd.init_kedu(mode="global", agent="codex", cwd=kedu_env["project"])
    init_cmd.init_kedu(mode="global", agent="kiro", cwd=kedu_env["project"])
    assert (agent_home / ".agents" / "skills" / "kedu-log" / "SKILL.md").exists()
    assert (kiro_home / "skills" / "kedu-search" / "SKILL.md").exists()

    cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=("codex", "kiro"),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        dry_run=False,
    )

    assert not (agent_home / ".agents" / "skills" / "kedu-log").exists()
    assert not (agent_home / ".agents" / "skills" / "kedu-search").exists()
    assert not (kiro_home / "skills" / "kedu-log").exists()
    assert not (kiro_home / "skills" / "kedu-search").exists()


def test_user_cleanup_refuses_install_root_that_overlaps_record_store(kedu_env, tmp_path):
    home = kedu_env["home"]
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
    assert any("overlaps Kedu home" in item["reason"] for item in result.preserved)


def test_user_cleanup_removes_kedu_launch_agent(kedu_env, tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    launch_agents = home_dir / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    plist = launch_agents / "org.kedu.test.plist"
    plist.write_text("<plist><string>kedu maintain</string></plist>", encoding="utf-8")

    cleanup.cleanup(
        user=True,
        project_root=None,
        hosts=(),
        bin_dir=tmp_path / "bin",
        install_root=tmp_path / "install-root",
        dry_run=False,
    )

    assert not plist.exists()


def test_project_cleanup_preserves_project_kedu_when_short_records_exist(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=project)
    short = project / ".kedu" / "short.jsonl"
    short.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(user=False, project_root=project, hosts=("kiro",), dry_run=False)

    assert (project / ".kedu").exists()
    assert short.exists()
    assert not (project / ".kedu" / "config.json").exists()
    assert not (project / ".kiro" / "steering" / "kedu.md").exists()
    assert not (project / ".kiro" / "agents" / "kedu.json").exists()
    assert not (project / ".kiro" / "prompts" / "kedu-agent-prompt.md").exists()
    assert not (project / ".kiro" / "skills" / "kedu-log").exists()
    assert not (project / ".kiro" / "skills" / "kedu-search").exists()
    assert any("short=1" in item["reason"] for item in result.preserved)


def test_project_cleanup_removes_codex_skills(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    assert (project / ".agents" / "skills" / "kedu-log" / "SKILL.md").exists()

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".agents" / "skills" / "kedu-log").exists()
    assert not (project / ".agents" / "skills" / "kedu-search").exists()


def test_project_cleanup_removes_project_claude_skills(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="claude", cwd=project)
    settings = project / ".claude" / "settings.local.json"
    assert not settings.exists()

    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)

    assert not (project / ".claude" / "skills" / "kedu").exists()
    assert not (project / ".claude" / "skills" / "kedu-log").exists()
    assert not (project / ".claude" / "skills" / "kedu-search").exists()
    assert not settings.exists()


def test_project_cleanup_removes_claude_line_count_block_only(kedu_env):
    project = kedu_env["project"]
    (project / "CLAUDE.md").write_text(
        "\n".join(
            [
                "# User Claude Notes",
                "",
                "====kedu start ====",
                "## Kedu Session Records",
                "Use Kedu.",
                "====kedu stop line:2====",
                "",
                "Keep this Claude note.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cleanup.cleanup(user=False, project_root=project, hosts=("claude",), dry_run=False)

    updated = (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Kedu Session Records" not in updated
    assert "# User Claude Notes" in updated
    assert "Keep this Claude note." in updated


def test_project_cleanup_removes_project_kedu_when_only_global_long_records_exist(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    (project / ".kedu" / "short.jsonl").write_text("", encoding="utf-8")
    long_file = kedu_env["home"] / "long" / "repo.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".kedu").exists()
    assert long_file.exists()
    assert any("long=1" in item["reason"] for item in result.preserved)


def test_project_cleanup_removes_recent_empty_project_kedu(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="cursor", cwd=project)

    result = cleanup.cleanup(user=False, project_root=project, hosts=("cursor",), dry_run=False)

    assert not (project / ".kedu").exists()
    assert any(action.action == "remove_dir" and action.path.endswith(".kedu") for action in result.actions)


def test_project_cleanup_removes_empty_project_kedu_regardless_of_age(kedu_env):
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    old_time = datetime(2025, 11, 13).timestamp()
    for path in sorted((project / ".kedu").rglob("*"), reverse=True):
        os.utime(path, (old_time, old_time))
    os.utime(project / ".kedu", (old_time, old_time))

    result = cleanup.cleanup(
        user=False,
        project_root=project,
        hosts=("codex",),
        dry_run=False,
    )

    assert not (project / ".kedu").exists()
    assert any(action.action == "remove_dir" and action.path.endswith(".kedu") for action in result.actions)


def test_project_cleanup_removes_codex_block_only(kedu_env):
    project = kedu_env["project"]
    content = "\n".join(
        [
            "# Local Instructions",
            "",
            cleanup.KEDU_BLOCK_START,
            "## Kedu Session Records",
            cleanup.KEDU_BLOCK_END,
            "",
            "Keep this project note.",
            "",
        ]
    )
    (project / "AGENTS.md").write_text(content, encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    updated = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "Kedu Session Records" not in updated
    assert "# Local Instructions" in updated
    assert "Keep this project note." in updated


def test_cleanup_scans_project_roots_and_prunes_to_short(kedu_env, tmp_path):
    scan_root = tmp_path / "scan-root"
    project_a = scan_root / "project-a"
    project_b = scan_root / "nested" / "project-b"
    project_a.mkdir(parents=True)
    project_b.mkdir(parents=True)
    init_cmd.init_kedu(mode="local", agent="kiro", cwd=project_a)
    init_cmd.init_kedu(mode="local", agent="claude", cwd=project_b)
    (project_a / ".kedu" / "short.jsonl").write_text(json.dumps({"id": "a:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(
        user=False,
        project_root=None,
        hosts=("claude", "kiro"),
        scan_projects=True,
        scan_roots=[scan_root],
        dry_run=False,
    )

    assert (project_a / ".kedu" / "short.jsonl").exists()
    assert not (project_a / ".kedu" / "config.json").exists()
    assert not (project_a / ".kiro" / "agents" / "kedu.json").exists()
    assert not (project_b / ".kedu").exists()
    assert not (project_b / ".claude" / "skills" / "kedu").exists()
    assert not result.warnings


def test_user_cleanup_removes_runtime_lock_but_preserves_records(kedu_env, tmp_path):
    home = kedu_env["home"]
    home.mkdir(parents=True, exist_ok=True)
    lock = home / ".kedu.lock"
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


def test_cleanup_scans_multiple_projects_and_preserves_short(kedu_env, tmp_path):
    scan_root = tmp_path / "scan-root"
    project_a = scan_root / "project-a"
    project_b = scan_root / "project-b"
    for project in (project_a, project_b):
        skill_dir = project / ".claude" / "skills" / "kedu-log"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("Kedu skill", encoding="utf-8")
        kedu_dir = project / ".kedu"
        kedu_dir.mkdir(parents=True)
        (kedu_dir / "short.jsonl").write_text(json.dumps({"id": "x:1"}) + "\n", encoding="utf-8")

    result = cleanup.cleanup(
        user=False,
        project_root=None,
        scan_projects=True,
        scan_roots=[scan_root],
        dry_run=False,
    )

    assert not (project_a / ".claude" / "skills" / "kedu-log").exists()
    assert not (project_b / ".claude" / "skills" / "kedu-log").exists()
    assert (project_a / ".kedu" / "short.jsonl").exists()
    assert (project_b / ".kedu" / "short.jsonl").exists()
    assert not result.warnings


def test_project_cleanup_refuses_when_project_kedu_is_global_store(tmp_path, monkeypatch):
    # Regression: running uninstall from a dir whose ".kedu" IS the global KEDU_HOME store
    # (e.g. from $HOME) previously rm -rf'd ~/.kedu, destroying long/ and archive/.
    store = tmp_path / ".kedu"
    long_dir = store / "long"
    archive_dir = store / "archive" / "project=proj" / "month=2026-01"
    long_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    long_file = long_dir / "proj.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    (archive_dir / "entries.parquet").write_text("archive", encoding="utf-8")
    monkeypatch.setenv("KEDU_HOME", str(store))

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


def test_full_uninstall_refuses_when_project_kedu_is_global_store(tmp_path, monkeypatch):
    store = tmp_path / ".kedu"
    long_dir = store / "long"
    archive_dir = store / "archive" / "project=proj" / "month=2026-01"
    long_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    long_file = long_dir / "proj.jsonl"
    long_file.write_text(json.dumps({"id": "session-1:1"}) + "\n", encoding="utf-8")
    (archive_dir / "entries.parquet").write_text("archive", encoding="utf-8")
    monkeypatch.setenv("KEDU_HOME", str(store))

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


def test_normal_project_cleanup_still_prunes_when_store_is_separate(kedu_env):
    # Guard must not affect genuine projects whose .kedu is unrelated to KEDU_HOME.
    project = kedu_env["project"]
    init_cmd.init_kedu(mode="local", agent="codex", cwd=project)
    (project / ".kedu" / "config.json").write_text(
        json.dumps({"project": "repo"}), encoding="utf-8"
    )
    (project / ".kedu" / "short.jsonl").write_text("", encoding="utf-8")

    cleanup.cleanup(user=False, project_root=project, hosts=("codex",), dry_run=False)

    assert not (project / ".kedu").exists()


def test_uninstall_cli_scans_projects_by_default():
    args = cleanup_cli_args(["uninstall"])
    assert args.scan_projects is True


def test_uninstall_cli_no_scan_projects_opt_out():
    args = cleanup_cli_args(["uninstall", "--no-scan-projects"])
    assert args.scan_projects is False


def test_cmd_uninstall_user_only_disables_scan(kedu_env, tmp_path, monkeypatch):
    from scripts import kedu as kedu_mod

    captured = {}

    def fake_cleanup(**kwargs):
        captured.update(kwargs)
        return cleanup.CleanupResult(dry_run=True)

    monkeypatch.setattr(kedu_mod.cleanup_mod, "cleanup", fake_cleanup)
    args = kedu_mod.build_parser().parse_args(["uninstall", "--user-only"])
    assert kedu_mod.cmd_uninstall(args) == 0
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


def test_uninstall_prints_human_readable_output(kedu_env, tmp_path, capsys):
    from scripts import kedu as kedu_mod

    install_root = kedu_env["home"] / "kedu"
    install_root.mkdir(parents=True)
    (install_root / "README.md").write_text("installed copy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "kedu").write_text(f'exec "{install_root}/.venv/bin/kedu" "$@"\n', encoding="utf-8")

    args = kedu_mod.build_parser().parse_args([
        "uninstall",
        "--user-only",
        "--hosts", "codex",
        "--bin-dir", str(bin_dir),
        "--install-root", str(install_root),
    ])
    rc = kedu_mod.cmd_uninstall(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "kedu uninstall" in out
    assert "Removed:" in out
    assert "Summary:" in out
    assert "{" not in out  # no raw JSON


def test_init_cli_supports_place_alias():
    from scripts import kedu

    args = kedu.build_parser().parse_args(["init", "--host", "claude", "--place", "global"])
    assert args.place == "global"


def cleanup_cli_args(argv):
    from scripts import kedu

    return kedu.build_parser().parse_args(argv)
