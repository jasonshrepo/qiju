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
    assert (home / "query_log.jsonl").exists()
    assert (home / "redaction_log.jsonl").exists()
    assert any("never removed" in item["reason"] for item in result.preserved)


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
    assert not (project / ".kedu" / "STATE.md").exists()
    assert not (project / ".kedu" / "config.json").exists()
    assert not (project / ".kiro" / "steering" / "kedu.md").exists()
    assert not (project / ".kiro" / "agents" / "kedu.json").exists()
    assert not (project / ".kiro" / "prompts" / "kedu-agent-prompt.md").exists()
    assert not (project / ".kiro" / "skills" / "kedu").exists()
    assert any("short=1" in item["reason"] for item in result.preserved)


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
