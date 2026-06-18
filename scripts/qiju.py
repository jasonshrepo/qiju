#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from . import capture, cleanup as cleanup_mod, init_cmd, maintain as maintain_mod, migrate as migrate_mod, paths as paths_mod, retro_redact, schema, search, storage
except ImportError:  # pragma: no cover
    import capture  # type: ignore
    import cleanup as cleanup_mod  # type: ignore
    import init_cmd  # type: ignore
    import maintain as maintain_mod  # type: ignore
    import migrate as migrate_mod  # type: ignore
    import paths as paths_mod  # type: ignore
    import retro_redact  # type: ignore
    import schema  # type: ignore
    import search  # type: ignore
    import storage  # type: ignore


# Keep in sync with pyproject.toml [project].version
QIJU_VERSION = "0.4.0"


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _parse_fields(spec: str | None) -> list[str] | None:
    if not spec:
        return None
    fields = [field.strip() for field in spec.split(",") if field.strip()]
    return fields or None


def _project_entry(entry: dict, fields: list[str] | None) -> dict:
    if not fields:
        return entry
    return {field: entry.get(field) for field in fields}


def _cell(value) -> str:
    if isinstance(value, (list, tuple)):
        return "; ".join(_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = "" if value is None else str(value)
    return " ".join(text.split())


def _print_table(rows: list[dict], columns: list[str]) -> None:
    widths = {column: len(column) for column in columns}
    rendered: list[dict[str, str]] = []
    for row in rows:
        cells = {column: _cell(row.get(column)) for column in columns}
        for column in columns:
            widths[column] = max(widths[column], len(cells[column]))
        rendered.append(cells)

    def _line(values: dict[str, str]) -> str:
        # Do not pad the final column, to avoid trailing whitespace bloat.
        return "  ".join(
            values[column].ljust(widths[column]) if i < len(columns) - 1 else values[column]
            for i, column in enumerate(columns)
        )

    print(_line({column: column for column in columns}))
    print(_line({column: "-" * widths[column] for column in columns}))
    for cells in rendered:
        print(_line(cells))


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
        print(f"qiju log: {exc}", file=sys.stderr)
        return 1


def _print_init_result(results: list[dict], *, mode: str) -> None:
    print(f"qiju init ({mode})")
    for result in results:
        print()
        project = result.get("project")
        header = f"[{result['host']}]"
        print(f"{header} project: {project}" if project else header)
        if result.get("project_root"):
            print(f"  root: {result['project_root']}")
        print(f"  home: {result['qiju_home']}")
        files = result.get("files") or []
        if files:
            print("  Files:")
            for path in files:
                print(f"    {path}")
        for message in result.get("messages") or []:
            print(f"  note: {message}")
    print()
    hosts = ", ".join(result["host"] for result in results)
    total_files = sum(len(result.get("files") or []) for result in results)
    plural = "host" if len(results) == 1 else "hosts"
    print(f"Summary: {len(results)} {plural} wired ({hosts}), {total_files} files written")


def cmd_init(args: argparse.Namespace) -> int:
    try:
        mode = args.place or ("global" if args.global_init else "local")
        if args.global_init and (args.local_init or args.place == "local"):
            raise ValueError("--global conflicts with --local/--place local")
        if args.local_init and args.place == "global":
            raise ValueError("--local conflicts with --place global")
        # Empty host -> single auto-detected init; "all"/comma list -> one init per host.
        hosts: tuple[str | None, ...] = init_cmd.parse_hosts(args.host) or (None,)
        results = [
            init_cmd.init_qiju(mode=mode, project=args.project, agent=host).as_dict()
            for host in hosts
        ]
        if args.json:
            _print_json(results[0] if len(results) == 1 else results)
        else:
            _print_init_result(results, mode=mode)
        return 0
    except Exception as exc:
        print(f"qiju init: {exc}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    try:
        results = search.search_entries(
            scope=args.scope,
            query=args.query,
            session=args.session,
            project=args.project,
            tags=args.tags or [],
            since=args.since,
            until=args.until,
            source=args.source,
            agent=args.agent,
            limit=args.limit,
            ids_only=args.ids_only,
            regex=args.regex,
            sort=args.sort,
            order=args.order,
        )
        fields = _parse_fields(args.fields)
        if args.format == "actions":
            for text, source in search.rollup_next_steps(results):
                date = _cell(source.get("ts"))[:10]
                title = _cell(source.get("title"))
                print(f'- [ ] {_cell(text)}  (from: {date} "{title}")')
        elif args.format == "table":
            _print_table(results, fields or ["ts", "id", "title"])
        elif args.format == "jsonl":
            for entry in results:
                print(json.dumps(_project_entry(entry, fields), ensure_ascii=False, sort_keys=True))
        elif args.format == "summary":
            for entry in results:
                print(f"{entry.get('ts', '')} {entry.get('project', '')} {entry.get('id', '')} {entry.get('title', '')}")
        else:
            _print_json([_project_entry(entry, fields) for entry in results] if fields else results)
        return 0
    except Exception as exc:
        print(f"qiju search: {exc}", file=sys.stderr)
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    entry = search.show_entry(args.id, project=args.project)
    if entry is None:
        if ":" not in args.id:
            print(
                f"qiju show: record not found: {args.id}\n"
                f"  Hint: ids carry a :N suffix (e.g. {args.id}:1). "
                f"Run 'qiju search' to find the exact id.",
                file=sys.stderr,
            )
        else:
            print(
                f"qiju show: record not found: {args.id}\n"
                f"  Hint: Run 'qiju search' to find the exact id.",
                file=sys.stderr,
            )
        return 1
    _print_json(_project_entry(entry, _parse_fields(args.fields)))
    return 0


def cmd_redact(args: argparse.Namespace) -> int:
    if not args.value or not args.value.strip():
        print(
            "qiju redact: --value must be a non-empty, non-whitespace string; "
            "an empty value would corrupt every record",
            file=sys.stderr,
        )
        return 1
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
        print(f"qiju redact: {exc}", file=sys.stderr)
        return 1


def cmd_maintain(args: argparse.Namespace) -> int:
    try:
        result = maintain_mod.maintain(project=args.project, dry_run=args.dry_run)
        _print_json(result)
        return 0
    except Exception as exc:
        print(f"qiju maintain: {exc}", file=sys.stderr)
        return 1


def _print_uninstall_result(result: cleanup_mod.CleanupResult) -> None:
    label = "dry-run" if result.dry_run else "uninstall"
    print(f"qiju {label}")
    print()
    if result.actions:
        print("Removed:")
        for action in result.actions:
            if action.executed or result.dry_run:
                verb = {"remove_file": "file", "remove_dir": "dir", "remove_qiju_block": "block"}.get(action.action, action.action)
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
        scan_projects = bool(args.scan_projects) and not args.user_only
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
        print(f"qiju uninstall: {exc}", file=sys.stderr)
        return 1


def cmd_migrate(args: argparse.Namespace) -> int:
    try:
        if getattr(args, "from_kedu", False):
            report = migrate_mod.migrate_from_kedu(
                project_root=args.project_root or os.getcwd(),
                dry_run=args.dry_run,
            )
        else:
            report = migrate_mod.migrate_project_names(
                project=args.project,
                dry_run=args.dry_run,
            )
        _print_json(report)
        return 0
    except Exception as exc:
        print(f"qiju migrate: {exc}", file=sys.stderr)
        return 1


def cmd_projects(args: argparse.Namespace) -> int:
    try:
        projects = storage.all_projects(paths_mod.qiju_home())
        for project in projects:
            print(project)
        return 0
    except Exception as exc:
        print(f"qiju projects: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qiju")
    parser.add_argument("--version", action="version", version=f"qiju {QIJU_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Enable Qiju for a host; project-local by default")
    init_parser.add_argument("--host", help="Host(s) to wire: claude, kiro, codex, cursor; 'all'; or a comma list, e.g. claude,codex")
    init_parser.add_argument("--global", dest="global_init", action="store_true", help="Install user-level host defaults instead of project-local files")
    init_parser.add_argument("--local", dest="local_init", action="store_true", help="Explicitly install project-local files")
    init_parser.add_argument("--place", choices=("local", "global"), help="Alias for selecting local or global init")
    init_parser.add_argument("--project", help="Project slug override")
    init_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of the human-readable summary")
    init_parser.set_defaults(func=cmd_init)

    log_parser = subparsers.add_parser("log", help="Capture a structured Qiju record")
    log_parser.add_argument("--source", required=True, choices=schema.VALID_SOURCES)
    log_parser.add_argument("--agent", help="Agent/host identity, e.g. claude-code, codex, kiro")
    log_parser.add_argument("--project")
    log_parser.add_argument("--body", help="Path to JSON entry. Reads stdin when omitted.")
    log_parser.add_argument("--session-id")
    log_parser.set_defaults(func=cmd_log)

    search_parser = subparsers.add_parser("search", help="Find candidate Qiju records")
    search_parser.add_argument("--scope", default="current_project")
    search_parser.add_argument("--project")
    search_parser.add_argument("--query")
    search_parser.add_argument("--session", help="Filter to all records with the given session UUID prefix")
    search_parser.add_argument("--tags", action="append")
    search_parser.add_argument("--since")
    search_parser.add_argument("--until")
    search_parser.add_argument("--source", choices=schema.VALID_SOURCES)
    search_parser.add_argument("--agent", help="Filter by agent/host identity")
    search_parser.add_argument("--limit", type=int)
    search_parser.add_argument("--ids-only", action="store_true")
    search_parser.add_argument("--regex", action="store_true")
    search_parser.add_argument("--fields", help="Comma-separated fields to keep, e.g. title,ts,next_steps")
    search_parser.add_argument("--sort", default="ts", help="Field to sort by (default: ts)")
    search_parser.add_argument("--order", choices=("asc", "desc"), default="desc", help="Sort order (default: desc)")
    search_parser.add_argument("--format", choices=("json", "jsonl", "summary", "table", "actions"), default="json")
    search_parser.set_defaults(func=cmd_search)

    show_parser = subparsers.add_parser("show", help="Hydrate one Qiju record by id")
    show_parser.add_argument("id")
    show_parser.add_argument("--project")
    show_parser.add_argument("--fields", help="Comma-separated fields to keep, e.g. title,ts,next_steps")
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

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove Qiju installation files without deleting records")
    uninstall_scope = uninstall_parser.add_mutually_exclusive_group()
    uninstall_scope.add_argument("--user-only", action="store_true", help="Remove only user-level install files and global host integrations")
    uninstall_scope.add_argument("--project-only", action="store_true", help="Remove only project-local Qiju integration")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Preview actions without removing files")
    uninstall_parser.add_argument("--project-root", "--project-path", dest="project_root", help="Project root to clean; defaults to the current directory")
    uninstall_parser.add_argument("--project", help="Project slug override")
    uninstall_parser.add_argument("--hosts", default="all", help="all or comma list: claude,kiro,codex,cursor")
    uninstall_parser.add_argument("--scan-projects", action=argparse.BooleanOptionalAction, default=True, help="Scan common project roots and clean ALL discovered Qiju-enabled projects (default: on). Use --no-scan-projects to clean only the current project.")
    uninstall_parser.add_argument("--scan-root", action="append", help="Root to scan for Qiju-enabled projects; can be repeated")
    uninstall_parser.add_argument("--scan-depth", type=int, default=cleanup_mod.DEFAULT_SCAN_DEPTH, help="Maximum scan depth for project discovery")
    uninstall_parser.add_argument("--bin-dir", help="Qiju shim directory, default: ~/.local/bin")
    uninstall_parser.add_argument("--install-root", help="Installed Qiju engine path, default: ~/.qiju/qiju")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    migrate_parser = subparsers.add_parser("migrate", help="Normalize project names to lowercase across stored records (one-time migration)")
    migrate_parser.add_argument("--project", help="Limit migration to one project slug")
    migrate_parser.add_argument("--from-kedu", dest="from_kedu", action="store_true", help="One-time brand migration: copy the legacy ~/.kedu store into ~/.qiju, rewriting kedu->qiju in every record (slugs, tags, bodies). The legacy store is preserved as a backup.")
    migrate_parser.add_argument("--project-root", dest="project_root", help="With --from-kedu, the project root whose local .kedu dir to migrate (defaults to cwd)")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing anything")
    migrate_parser.set_defaults(func=cmd_migrate)

    projects_parser = subparsers.add_parser("projects", help="List known project slugs")
    projects_parser.set_defaults(func=cmd_projects)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
