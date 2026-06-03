from __future__ import annotations

from scripts import kedu


def test_cli_program_is_kedu():
    parser = kedu.build_parser()
    assert parser.prog == "kedu"


def test_init_cli_is_local_first_with_host():
    args = kedu.build_parser().parse_args(["init", "--host", "codex"])
    assert args.host == "codex"
    assert args.global_init is False


def test_init_cli_supports_optional_global():
    args = kedu.build_parser().parse_args(["init", "--host", "kiro", "--global"])
    assert args.host == "kiro"
    assert args.global_init is True
