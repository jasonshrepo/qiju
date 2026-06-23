# Qiju Host Integration

Qiju supports existing coding agents by installing portable Agent Skills. The
skills tell the agent when and how to call the `qiju` CLI. The CLI writes and
retrieves records.

Qiju is not an agent framework and does not orchestrate hosts.

## Supported hosts

| Host | Local skill location | Global skill location | Invocation |
| --- | --- | --- | --- |
| Claude Code | `.claude/skills/<skill>/SKILL.md` | `~/.claude/skills/<skill>/SKILL.md` | `/qiju-log`, `/qiju-search`, `/qiju-review` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `~/.agents/skills/<skill>/SKILL.md` | `$qiju-log`, `$qiju-search`, `$qiju-review` |
| Kiro | `.kiro/skills/<skill>/SKILL.md` | `~/.kiro/skills/<skill>/SKILL.md` | `/qiju-log`, `/qiju-search`, `/qiju-review` |
| Cursor | `.cursor/skills/<skill>/SKILL.md` | `~/.cursor/skills/<skill>/SKILL.md` | `/qiju-log`, `/qiju-search`, `/qiju-review` |

Installed skills:

- `qiju-log` - write a verified session handoff record;
- `qiju-search` - retrieve previous decisions, unresolved work, and next steps;
- `qiju-review` - review recent records for lessons and prompt improvements.

## Wiring a project

```bash
cd /path/to/project
qiju init --host claude
qiju init --host codex
```

Or wire multiple hosts at once:

```bash
qiju init --host claude,codex
qiju init --host all
```

`qiju init` creates `.qiju/config.json`, `.qiju/short.jsonl`, host-specific skill
files, and a project registry entry under `~/.qiju/registry.d/`.

## Updating skills after an upgrade

```bash
uv tool upgrade qiju
qiju update --dry-run
qiju update
```

For older installs that predate the registry:

```bash
qiju update --scan-projects
```

Use `--host claude`, `--host codex`, `--host kiro`, `--host cursor`, or a comma
list to refresh only selected hosts.

## Removing integration files

```bash
qiju uninstall --dry-run
qiju uninstall --hosts codex --project-only
qiju uninstall --user-only
```

Default uninstall behavior preserves records. It removes integration/runtime
files, prunes generated project metadata, and preserves `.qiju/short.jsonl`,
`~/.qiju/long`, `~/.qiju/archive`, and `~/.qiju/redaction_log.jsonl` when present.

Use `qiju uninstall --purge-data` only when you explicitly want to delete durable
record history.

