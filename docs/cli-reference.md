# Qiju CLI Reference

Run `qiju --help` for the live command list.

```text
qiju init
qiju log
qiju temp-entry
qiju search
qiju show
qiju redact
qiju maintain
qiju update
qiju uninstall
qiju migrate
qiju projects
```

## init

Enable Qiju for a supported host. Project-local is the default.

```bash
qiju init --host claude
qiju init --host claude,codex
qiju init --host all
qiju init --host codex --global
qiju init --host cursor --json
```

Options include `--host`, `--global`, `--local`, `--place local|global`,
`--project`, and `--json`.

Supported hosts are `claude`, `codex`, `kiro`, and `cursor`.

## log

Capture a structured Qiju record.

```bash
qiju log --source manual --agent codex --body .qiju/tmp/qiju-entry.codex.<id>.json --cleanup
```

Options include `--source manual|agent`, `--agent`, `--project`, `--body`,
`--cleanup`, and `--session-id`. When `--body` is omitted, `qiju log` reads JSON
from stdin.

## temp-entry

Allocate a unique workspace-local staging file for `qiju log`.

```bash
qiju temp-entry --agent claude
```

The returned path is under `.qiju/tmp/`.

## search

Find candidate records.

```bash
qiju search --scope current_project --query "auth cookie"
qiju search --scope all --tags security --since 2026-01-01 --format summary
qiju search --query "token.*expiry" --regex --ids-only
qiju search --format actions
```

Options include `--scope`, `--project`, `--query`, `--session`, `--tags`,
`--since`, `--until`, `--source`, `--agent`, `--limit`, `--ids-only`,
`--regex`, `--fields`, `--sort`, `--order`, and `--format`.

Formats are `json`, `jsonl`, `summary`, `table`, and `actions`.

## show

Hydrate one record by exact ID.

```bash
qiju show '<uuid>:1'
qiju show '<uuid>:1' --fields title,next_steps,body_md
```

Pass the ID exactly as `qiju search` prints it, including the `:N` suffix.

## maintain

Rotate short-tier records, sweep stale staging files, and archive old durable
records.

```bash
qiju maintain --dry-run
qiju maintain --project my-project
```

## redact

Retroactively scrub a known literal value.

```bash
qiju redact --value "secret-value" --reason "leaked in session"
```

Options include `--value`, `--reason`, `--placeholder`, and `--project`.

Redaction is best-effort. Avoid recording secrets in the first place.

## migrate

Normalize stored project names, or copy a legacy Kedu store into Qiju.

```bash
qiju migrate --dry-run
qiju migrate --project MyProject
qiju migrate --from-kedu --project-root /path/to/project --dry-run
```

The Kedu migration copies from `~/.kedu` to `~/.qiju` and preserves the legacy
store as a backup.

## update

Refresh Qiju skill files in registered projects after upgrading the CLI.

```bash
uv tool upgrade qiju
qiju update --dry-run
qiju update
qiju update --host claude
qiju update --scan-projects
```

By default, `qiju update` is registry-first and uses `~/.qiju/registry.d/`.
Use `--scan-projects` once to discover existing Qiju projects and backfill the
registry.

## uninstall

Remove integration files without deleting records by default.

```bash
qiju uninstall --dry-run
qiju uninstall --hosts kiro
qiju uninstall --hosts kiro,cursor --project-only
qiju uninstall --no-scan-projects
qiju uninstall --user-only
```

`--purge-data` is a separate destructive path that deletes durable records under
`~/.qiju/long` and `~/.qiju/archive`; it requires confirmation unless `--yes` is
provided.

## projects

List known project slugs.

```bash
qiju projects
```

