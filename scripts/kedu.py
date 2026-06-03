#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

try:
    from . import capture, cleanup as cleanup_mod, init_cmd, maintain as maintain_mod, paths as paths_mod, retro_redact, schema, search, state
except ImportError:  # pragma: no cover
    import capture  # type: ignore
    import cleanup as cleanup_mod  # type: ignore
    import init_cmd  # type: ignore
    import maintain as maintain_mod  # type: ignore
    import paths as paths_mod  # type: ignore
    import retro_redact  # type: ignore
    import schema  # type: ignore
    import search  # type: ignore
    import state  # type: ignore


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_log(args: argparse.Namespace) -> int:
    try:
        raw = capture.read_entry(args.body)
        entry_id = capture.log_entry(
            raw,
            source=args.source,
            project=args.project,
            agent=args.agent,
            session_id=args.session_id,
        )
        print(entry_id)
        return 0
    except (ValueError, schema.ValidationError, OSError, json.JSONDecodeError) as exc:
        print(f"kedu log: {exc}", file=sys.stderr)
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    try:
        mode = args.place or ("global" if args.global_init else "local")
        if args.global_init and (args.local_init or args.place == "local"):
            raise ValueError("--global conflicts with --local/--place local")
        if args.local_init and args.place == "global":
            raise ValueError("--local conflicts with --place global")
        result = init_cmd.init_kedu(
            mode=mode,
            project=args.project,
            agent=args.host,
        )
        _print_json(result.as_dict())
        return 0
    except Exception as exc:
        print(f"kedu init: {exc}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    try:
        results = search.search_entries(
            scope=args.scope,
            query=args.query,
            project=args.project,
            tags=args.tags or [],
            since=args.since,
            until=args.until,
            source=args.source,
            agent=args.agent,
            limit=args.limit,
            ids_only=args.ids_only,
            regex=args.regex,
        )
        if args.format == "jsonl":
            for entry in results:
                print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        elif args.format == "summary":
            for entry in results:
                print(f"{entry.get('ts', '')} {entry.get('project', '')} {entry.get('id', '')} {entry.get('title', '')}")
        else:
            _print_json(results)
        return 0
    except Exception as exc:
        print(f"kedu search: {exc}", file=sys.stderr)
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    entry = search.show_entry(args.id, project=args.project)
    if entry is None:
        print(f"kedu show: record not found: {args.id}", file=sys.stderr)
        return 1
    _print_json(entry)
    return 0


def cmd_redact(args: argparse.Namespace) -> int:
    try:
        event = retro_redact.redact_value_everywhere(
            value=args.value,
            reason=args.reason,
            placeholder=args.placeholder,
            project=args.project,
        )
        _print_json(event)
        return 0
    except Exception as exc:
        print(f"kedu redact: {exc}", file=sys.stderr)
        return 1


def cmd_maintain(args: argparse.Namespace) -> int:
    try:
        result = maintain_mod.maintain(project=args.project, dry_run=args.dry_run)
        _print_json(result)
        return 0
    except Exception as exc:
        print(f"kedu maintain: {exc}", file=sys.stderr)
        return 1


def _print_uninstall_result(result: cleanup_mod.CleanupResult) -> None:
    label = "dry-run" if result.dry_run else "uninstall"
    print(f"kedu {label}")
    print()
    if result.actions:
        print("Removed:")
        for action in result.actions:
            if action.executed or result.dry_run:
                verb = {"remove_file": "file", "remove_dir": "dir", "remove_kedu_block": "block"}.get(action.action, action.action)
                print(f"  [{verb}] {action.path}")
    else:
        print("  (nothing to remove)")
    if result.preserved:
        print()
        print("Preserved:")
        for item in result.preserved:
            print(f"  {item['path']}")
            print(f"    reason: {item['reason']}")
    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"  {warning}")
    print()
    removed = sum(1 for a in result.actions if a.executed or result.dry_run)
    print(f"Summary: {removed} removed, {len(result.preserved)} preserved")


def cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        user = not args.project_only
        project_root = None if args.user_only else (args.project_root or ".")
        scan_projects = bool(args.scan_projects)
        result = cleanup_mod.cleanup(
            user=user,
            project_root=project_root,
            project=args.project,
            hosts=cleanup_mod.parse_hosts(args.hosts),
            bin_dir=args.bin_dir,
            install_root=args.install_root,
            scan_projects=scan_projects,
            scan_roots=args.scan_root,
            scan_depth=args.scan_depth,
            dry_run=args.dry_run,
        )
        _print_uninstall_result(result)
        return 0
    except Exception as exc:
        print(f"kedu uninstall: {exc}", file=sys.stderr)
        return 1


def cmd_rebuild_state(args: argparse.Namespace) -> int:
    try:
        path = state.rebuild_state(project=args.project)
        print(path)
        return 0
    except Exception as exc:
        print(f"kedu rebuild-state: {exc}", file=sys.stderr)
        return 1


def cmd_state(args: argparse.Namespace) -> int:
    try:
        if args.rebuild:
            path = state.rebuild_state(project=args.project)
        else:
            path = paths_mod.resolve_paths(project=args.project).state_md
        if not path.exists():
            path = state.rebuild_state(project=args.project)
        print(path.read_text(encoding="utf-8"), end="")
        return 0
    except Exception as exc:
        print(f"kedu state: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kedu")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Enable Kedu for a host; project-local by default")
    init_parser.add_argument("--host", choices=init_cmd.KNOWN_AGENTS, help="Host agent to wire: claude, kiro, codex, or cursor")
    init_parser.add_argument("--global", dest="global_init", action="store_true", help="Install user-level host defaults instead of project-local files")
    init_parser.add_argument("--local", dest="local_init", action="store_true", help="Explicitly install project-local files")
    init_parser.add_argument("--place", choices=("local", "global"), help="Alias for selecting local or global init")
    init_parser.add_argument("--project", help="Project slug override")
    init_parser.set_defaults(func=cmd_init)

    log_parser = subparsers.add_parser("log", help="Capture a structured Kedu record")
    log_parser.add_argument("--source", required=True, choices=schema.VALID_SOURCES)
    log_parser.add_argument("--agent", help="Agent/host identity, e.g. claude-code, codex, kiro")
    log_parser.add_argument("--project")
    log_parser.add_argument("--body", help="Path to JSON entry. Reads stdin when omitted.")
    log_parser.add_argument("--session-id")
    log_parser.set_defaults(func=cmd_log)

    search_parser = subparsers.add_parser("search", help="Find candidate Kedu records")
    search_parser.add_argument("--scope", default="current_project")
    search_parser.add_argument("--project")
    search_parser.add_argument("--query")
    search_parser.add_argument("--tags", action="append")
    search_parser.add_argument("--since")
    search_parser.add_argument("--until")
    search_parser.add_argument("--source", choices=schema.VALID_SOURCES)
    search_parser.add_argument("--agent", help="Filter by agent/host identity")
    search_parser.add_argument("--limit", type=int)
    search_parser.add_argument("--ids-only", action="store_true")
    search_parser.add_argument("--regex", action="store_true")
    search_parser.add_argument("--format", choices=("json", "jsonl", "summary"), default="json")
    search_parser.set_defaults(func=cmd_search)

    show_parser = subparsers.add_parser("show", help="Hydrate one Kedu record by id")
    show_parser.add_argument("id")
    show_parser.add_argument("--project")
    show_parser.set_defaults(func=cmd_show)

    redact_parser = subparsers.add_parser("redact", help="Retroactively scrub a literal value")
    redact_parser.add_argument("--value", required=True)
    redact_parser.add_argument("--reason", required=True)
    redact_parser.add_argument("--placeholder", default="[REDACTED:manual]")
    redact_parser.add_argument("--project")
    redact_parser.set_defaults(func=cmd_redact)

    maintain_parser = subparsers.add_parser("maintain", help="Rotate short tier and archive long tier")
    maintain_parser.add_argument("--project")
    maintain_parser.add_argument("--dry-run", action="store_true")
    maintain_parser.set_defaults(func=cmd_maintain)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove Kedu installation files without deleting records")
    uninstall_scope = uninstall_parser.add_mutually_exclusive_group()
    uninstall_scope.add_argument("--user-only", action="store_true", help="Remove only user-level install files and global host integrations")
    uninstall_scope.add_argument("--project-only", action="store_true", help="Remove only project-local Kedu integration")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Preview actions without removing files")
    uninstall_parser.add_argument("--project-root", "--project-path", dest="project_root", help="Project root to clean; defaults to the current directory")
    uninstall_parser.add_argument("--project", help="Project slug override")
    uninstall_parser.add_argument("--hosts", default="all", help="all or comma list: claude,kiro,codex,cursor")
    uninstall_parser.add_argument("--scan-projects", action="store_true", help="Also scan common project roots and clean all discovered Kedu-enabled projects")
    uninstall_parser.add_argument("--scan-root", action="append", help="Root to scan for Kedu-enabled projects; can be repeated")
    uninstall_parser.add_argument("--scan-depth", type=int, default=cleanup_mod.DEFAULT_SCAN_DEPTH, help="Maximum scan depth for project discovery")
    uninstall_parser.add_argument("--bin-dir", help="Kedu shim directory, default: ~/.local/bin")
    uninstall_parser.add_argument("--install-root", help="Installed Kedu engine path, default: ~/.kedu/kedu")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    state_view_parser = subparsers.add_parser("state", help="Print .kedu/STATE.md")
    state_view_parser.add_argument("--project")
    state_view_parser.add_argument("--rebuild", action="store_true", help="Regenerate before printing")
    state_view_parser.set_defaults(func=cmd_state)

    state_parser = subparsers.add_parser("rebuild-state", help="Regenerate .kedu/STATE.md")
    state_parser.add_argument("--project")
    state_parser.set_defaults(func=cmd_rebuild_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
