# Kedu / 刻牍

Kedu is a local-first, lossless session-record harness for AI coding agents.

It preserves verified development session records so Claude Code, Codex, Cursor, Kiro,
and future agents can resume work from developer-owned project history instead of relying
on platform-specific memory.

Kedu is not a vector memory system, not RAG, and not a search engine. It is a durable
handoff layer: capture what happened, preserve it locally, retrieve candidate records
deterministically, and let the model reason over verified context.

For the setup model, see [INSTALL_AND_AGENT_INIT.md](INSTALL_AND_AGENT_INIT.md).

## Install

```bash
bash install.sh
bash install.sh --install-launchd  # optional macOS scheduled maintenance
```

The central store defaults to `~/.kedu`. Override with:

```bash
export KEDU_HOME=/path/to/kedu-home
```

All agents share this one store. The system does not create per-agent stores; agent
identity is recorded on each Kedu record through the `agent` field.

By default, the installed engine copy lives under:

```text
~/.kedu/kedu
```

The `kedu` shim executes from that installed copy, so the downloaded checkout can be
deleted after installation.

## Initialize

Project-local setup is the default:

```bash
cd /path/to/project
kedu init --host codex
```

Supported hosts:

```bash
kedu init --host claude
kedu init --host kiro
kedu init --host codex
kedu init --host cursor
```

Optional user/global defaults can be added later:

```bash
kedu init --host codex --global
kedu init --host claude --place global
```

Project-local integrations write:

- Claude: appends a line-counted Kedu block to `CLAUDE.md`, registers a `SessionEnd` hook in `.claude/settings.local.json`, and writes the unified `/kedu` skill under `.claude/skills/kedu/`
- Codex: appends a Kedu block to `AGENTS.md`
- Kiro: writes `.kiro/steering/kedu.md`, `.kiro/hooks/kedu-clean-exit.kiro.hook`, `.kiro/agents/kedu.json`, and `.kiro/prompts/kedu-agent-prompt.md`
- Cursor: writes `.cursor/rules/kedu.mdc`

Claude `CLAUDE.md` sections are wrapped as:

```text
====kedu start ====
...
====kedu stop line:N====
```

`N` is the number of content lines written by Kedu. Uninstall removes only this marked
section and leaves the rest of `CLAUDE.md` intact.

In Claude Code, use one command surface:

```text
/kedu log
/kedu search <query>
/kedu <specific instruction about creating or retrieving durable memory>
```

For Kiro CLI, select the generated agent with:

```bash
kiro-cli --agent kedu chat
```

or make it the CLI default yourself:

```bash
kiro-cli agent set-default kedu
```

Kiro CLI does not reliably fire the Kiro `agentStop` hook when a CLI session quits. Log
explicitly before quitting. Kiro IDE can use the generated hook, but temporary entry JSON
should be written inside the workspace, such as `.kedu/kedu-entry.json`, not `/tmp`.

Each local init also creates:

```text
<project>/.kedu/
├── short.jsonl
├── STATE.md
└── config.json
```

If the project is a git repo, `.kedu/` is added to `.git/info/exclude`.

## Capture

```bash
kedu log --source manual --agent codex --project my-project --body /tmp/record.json
```

The record body is validated, redacted, then appended to:

- `<project-root>/.kedu/short.jsonl`
- `$KEDU_HOME/long/<project>.jsonl`

`--body` expects a path to a JSON file. If omitted, `kedu log` reads JSON from stdin.

## Search

```bash
kedu search --scope current_project --query "auth cookie"
kedu search --scope current_project --agent codex --query "auth cookie"
kedu search --scope all --tags security --since 2026-01-01
kedu search --scope current_project --query "deploy" --ids-only
kedu show '<session-id>:1'
```

Search is candidate identification, not search-engine ranking. Kedu uses structured
filters plus exact keyword/body scanning so the model can decide relevance over verified
records.

## State

```bash
kedu state --project my-project
kedu rebuild-state --project my-project
```

`.kedu/STATE.md` is a derived boot view with open items, active decisions, and an entry
index.

## Maintenance

```bash
kedu maintain --dry-run
kedu maintain
```

Maintenance rotates the 7-day hot project record and archives aged durable records to
Parquet.

## Uninstall

Preview the uninstall:

```bash
kedu uninstall --dry-run
```

Run the uninstall:

```bash
kedu uninstall
```

By default, uninstall removes the user-level install and generated Kedu wiring in the
current project. For unscoped `kedu uninstall`, it also scans common project roots for
Kedu-enabled projects and removes generated project wiring there too. Use `--user-only`,
`--project-only`, or `--no-project-scan` to narrow the scope. You can also target another
project with:

```bash
kedu uninstall --project-only --project-root /path/to/project --hosts kiro,codex --dry-run
kedu uninstall --dry-run --scan-root /path/to/projects
```

For Claude, uninstall removes only the marked Kedu block from `CLAUDE.md` and removes
the nested Kedu `SessionEnd` hook from Claude settings, leaving unrelated instructions
and settings intact.

Uninstall never removes shared record or audit data under `~/.kedu/long`,
`~/.kedu/archive`, `~/.kedu/query_log.jsonl`, or `~/.kedu/redaction_log.jsonl`. In
projects, uninstall preserves only local short records at `.kedu/short.jsonl`. Generated
project state such as `.kedu/STATE.md`, `.kedu/config.json`, and temporary entry files is
removed. If a project has no local short records, its `.kedu/` folder is removed; global
long/archive records remain untouched.

## Redaction

```bash
kedu redact --value "secret-value" --reason "leaked in session"
```

Secrets and PII are redacted before records are persisted. Retroactive redaction rewrites
JSONL and Parquet tiers and records an audit event.

## Priority Model

Kedu records are verified session handoff records and project history. Use them as the
source of truth for previous session progress, unresolved bugs, implementation decisions,
next steps, and what actually happened. Platform memories are weak background unless the
user explicitly verifies them.
