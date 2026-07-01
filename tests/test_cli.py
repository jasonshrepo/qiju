from __future__ import annotations

import pytest

from qiju import cli as qiju


def test_cli_program_is_qiju():
    parser = qiju.build_parser()
    assert parser.prog == "qiju"


def test_cli_version_flag(capsys):
    parser = qiju.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"qiju {qiju.get_version()}"


def test_cli_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert qiju.get_version() == data["project"]["version"]


def test_init_cli_is_local_first_with_host():
    args = qiju.build_parser().parse_args(["init", "--host", "codex"])
    assert args.host == "codex"
    assert args.global_init is False


def test_init_cli_supports_optional_global():
    args = qiju.build_parser().parse_args(["init", "--host", "kiro", "--global"])
    assert args.host == "kiro"
    assert args.global_init is True


def test_search_cli_output_shaping_defaults():
    args = qiju.build_parser().parse_args(["search", "--query", "x"])
    assert args.fields is None
    assert args.sort == "ts"
    assert args.order == "desc"
    assert args.format == "json"


def test_search_cli_accepts_table_and_shaping_flags():
    args = qiju.build_parser().parse_args(
        ["search", "--fields", "ts,title", "--sort", "title", "--order", "asc", "--format", "table"]
    )
    assert args.fields == "ts,title"
    assert args.sort == "title"
    assert args.order == "asc"
    assert args.format == "table"


def test_search_cli_accepts_session_filter():
    args = qiju.build_parser().parse_args(["search", "--session", "abcdef12"])
    assert args.session == "abcdef12"


def test_show_cli_accepts_fields():
    args = qiju.build_parser().parse_args(["show", "abc:1", "--fields", "title,next_steps"])
    assert args.fields == "title,next_steps"


def test_show_bare_uuid_not_found_message(qiju_env, capsys):
    # A bare UUID (no :N suffix) should produce a helpful error pointing to :N and qiju search.
    args = qiju.build_parser().parse_args(["show", "abcdef12"])
    rc = qiju.cmd_show(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert ":N" in err or ":1" in err
    assert "qiju search" in err


def test_temp_entry_prints_unique_staging_path(qiju_env, monkeypatch, capsys):
    monkeypatch.chdir(qiju_env["project"])
    args = qiju.build_parser().parse_args(["temp-entry", "--agent", "claude"])
    assert qiju.cmd_temp_entry(args) == 0
    first = capsys.readouterr().out.strip()
    from pathlib import Path

    p = Path(first)
    assert p.exists() and p.read_text() == ""
    assert p.parent.name == "tmp" and p.parent.parent.name == ".qiju"
    assert p.name.startswith("qiju-entry.claude.") and p.name.endswith(".json")

    assert qiju.cmd_temp_entry(args) == 0
    second = capsys.readouterr().out.strip()
    assert first != second


def _valid_entry_json():
    import json

    return json.dumps(
        {
            "title": "cleanup test",
            "tags": ["t"],
            "search_terms": ["s"],
            "next_steps": [],
            "body_md": "body",
        }
    )


def test_log_cleanup_deletes_staged_file_after_success(qiju_env, monkeypatch, capsys):
    from qiju import staging

    monkeypatch.chdir(qiju_env["project"])
    path = staging.allocate_staging(project=None, cwd=qiju_env["project"], agent="claude")
    path.write_text(_valid_entry_json(), encoding="utf-8")
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--agent", "claude", "--project", "repo", "--body", str(path), "--cleanup"]
    )
    assert qiju.cmd_log(args) == 0
    assert not path.exists()


def test_log_cleanup_keeps_file_on_failed_log(qiju_env, monkeypatch):
    from qiju import staging

    monkeypatch.chdir(qiju_env["project"])
    path = staging.allocate_staging(project=None, cwd=qiju_env["project"], agent="claude")
    path.write_text("not valid json", encoding="utf-8")
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--body", str(path), "--cleanup"]
    )
    assert qiju.cmd_log(args) == 1
    assert path.exists()  # never deleted because the log failed


def test_log_cleanup_refuses_non_staging_body(qiju_env, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(qiju_env["project"])
    body = tmp_path / "record.json"
    body.write_text(_valid_entry_json(), encoding="utf-8")
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--project", "repo", "--body", str(body), "--cleanup"]
    )
    assert qiju.cmd_log(args) == 0  # log succeeds
    assert body.exists()  # arbitrary user file not deleted
    assert "--cleanup skipped" in capsys.readouterr().err


def test_log_cleanup_refuses_symlink_body(qiju_env, monkeypatch, tmp_path):
    from qiju import paths, staging

    monkeypatch.chdir(qiju_env["project"])
    tmp = paths.resolve_paths(project=None, cwd=qiju_env["project"]).tmp_dir
    tmp.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "payload.json"
    target.write_text(_valid_entry_json(), encoding="utf-8")
    link = tmp / "qiju-entry.claude.link.json"
    link.symlink_to(target)
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--project", "repo", "--body", str(link), "--cleanup"]
    )
    assert qiju.cmd_log(args) == 0
    assert link.exists() and target.exists()  # symlink redirect refused


def test_log_cleanup_refuses_traversal_body(qiju_env, monkeypatch):
    from qiju import paths

    monkeypatch.chdir(qiju_env["project"])
    qiju_paths = paths.resolve_paths(project=None, cwd=qiju_env["project"])
    qiju_paths.tmp_dir.mkdir(parents=True, exist_ok=True)
    # A real, valid file one level above tmp/, reached via a `../` traversal that escapes
    # the staging dir. The log must succeed but cleanup must refuse (realpath lands outside).
    escaped = qiju_paths.project_qiju_dir / "qiju-entry.claude.evil.json"
    escaped.write_text(_valid_entry_json(), encoding="utf-8")
    traversal = qiju_paths.tmp_dir / ".." / "qiju-entry.claude.evil.json"
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--project", "repo", "--body", str(traversal), "--cleanup"]
    )
    assert qiju.cmd_log(args) == 0
    assert escaped.exists()  # traversal target not deleted


def test_log_cleanup_with_stdin_is_noop(qiju_env, monkeypatch, capsys):
    import io

    monkeypatch.chdir(qiju_env["project"])
    monkeypatch.setattr("sys.stdin", io.StringIO(_valid_entry_json()))
    args = qiju.build_parser().parse_args(
        ["log", "--source", "manual", "--project", "repo", "--cleanup"]
    )
    assert qiju.cmd_log(args) == 0  # log via stdin succeeds
    assert "--cleanup skipped" in capsys.readouterr().err  # nothing to clean, warned


def test_parse_fields_splits_and_trims():
    assert qiju._parse_fields("title, ts , next_steps") == ["title", "ts", "next_steps"]
    assert qiju._parse_fields("") is None
    assert qiju._parse_fields(None) is None
    assert qiju._parse_fields(" , ") is None


def test_project_entry_keeps_only_requested_fields():
    entry = {"id": "a:1", "title": "T", "ts": "2026", "body_md": "long"}
    assert qiju._project_entry(entry, ["title", "ts"]) == {"title": "T", "ts": "2026"}
    assert qiju._project_entry(entry, ["missing"]) == {"missing": None}
    assert qiju._project_entry(entry, None) is entry


def test_cell_flattens_lists_dicts_and_whitespace():
    assert qiju._cell(["a", "b"]) == "a; b"
    assert qiju._cell(None) == ""
    assert qiju._cell("multi\nline   text") == "multi line text"
    assert qiju._cell({"k": "v"}) == '{"k": "v"}'


def test_print_table_renders_header_and_rows(capsys):
    rows = [{"ts": "2026-06-04", "title": "Newer"}, {"ts": "2026-06-01", "title": "Older"}]
    qiju._print_table(rows, ["ts", "title"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["ts", "title"]
    assert set(lines[1]) == {"-", " "}
    assert "2026-06-04" in lines[2] and "Newer" in lines[2]
    assert "2026-06-01" in lines[3] and "Older" in lines[3]
