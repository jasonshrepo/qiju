from __future__ import annotations

import pytest

from scripts import qiju


def test_cli_program_is_qiju():
    parser = qiju.build_parser()
    assert parser.prog == "qiju"


def test_cli_version_flag(capsys):
    parser = qiju.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"qiju {qiju.QIJU_VERSION}"


def test_cli_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert qiju.QIJU_VERSION == data["project"]["version"]


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
