# Install And Host Init Model

QiJu has two separate setup steps.

## 1. Install QiJu

Run once per machine:

```bash
bash install.sh
```

This installs:

- `qiju` CLI
- shared store at `~/.qiju`
- installed engine copy at `~/.qiju/qiju`
- shared support templates under `~/.qiju/agents`

This step does not enable QiJu inside a specific project. The `qiju` command refers to the
installed engine copy, so the downloaded installer checkout can be deleted after
installation.

## 2. Enable A Project Host

Project-local setup is the first/default step:

```bash
cd /path/to/project
qiju init --host codex
```

Supported hosts:

- `claude`
- `kiro`
- `codex`
- `cursor`

Optional user/global defaults can be added later:

```bash
qiju init --host codex --global
```

When called from inside a supported agent, `--host` may be omitted if QiJu can detect the
host from the environment or project markers:

```bash
qiju init
```

## Scope Semantics

Local init means "enable QiJu for this host in the current project." It creates:

```text
<project>/.qiju/
├── short.jsonl
└── config.json
```

It also writes project-local host integration. QiJu is skill-first: each agent gets three
explicit skills — `qiju-log` (save a record), `qiju-search` (retrieve history), and
`qiju-review` (review recent records for lessons) — with no
always-on `CLAUDE.md` block and no `STATE.md`. The skills carry trigger-tuned descriptions
so the agent auto-discovers them; they mandate nothing on init.

- Claude: writes `.claude/skills/qiju-log/SKILL.md`, `.claude/skills/qiju-search/SKILL.md`, and `.claude/skills/qiju-review/SKILL.md`. No `CLAUDE.md` block.
- Codex: writes `.agents/skills/qiju-log/SKILL.md`, `.agents/skills/qiju-search/SKILL.md`, and `.agents/skills/qiju-review/SKILL.md`.
- Kiro: writes `.kiro/skills/qiju-log/SKILL.md`, `.kiro/skills/qiju-search/SKILL.md`, and `.kiro/skills/qiju-review/SKILL.md`. No Kiro agent config, no steering file, and no saved prompt.
- Cursor: writes `.cursor/skills/qiju-log/SKILL.md`, `.cursor/skills/qiju-search/SKILL.md`, and `.cursor/skills/qiju-review/SKILL.md`.

In Claude Code, Codex, Kiro, and Cursor, invoke the skills directly:

```text
/qiju-log
/qiju-search <query>
/qiju-review
```

If the project is a git repo, `.qiju/` is added to `.git/info/exclude`, not `.gitignore`.

Global init means "install optional user-level defaults for this host." It is not required
for a project to use QiJu.

QiJu intentionally does not create a provider-specific Kiro CLI agent. If you want a
selectable Kiro agent, create your own `.kiro/agents/qiju.json` after init and point it at
the installed `.kiro/skills/` entries according to Kiro's agent docs.

Kiro does not use automatic QiJu hooks. Log explicitly before ending work, and write
temporary entry JSON inside the workspace, such as `.qiju/qiju-entry.json`, not `/tmp`.

## Shared Store Rule

All agents share one store:

```text
~/.qiju/
├── long/
├── archive/
└── redaction_log.jsonl
```

There are no per-agent stores. Agent identity is stored per record:

```json
{
  "agent": "codex",
  "source": "manual"
}
```

`agent` answers "which host created this record?"

`source` answers "how was this record captured?" (`manual` or `agent`).

## Priority Policy

QiJu records are verified session handoff records and project history. Generated host
instructions should treat QiJu as the source of truth for:

- previous session progress
- active implementation decisions
- unresolved bugs
- previous attempts
- next steps
- what actually happened in prior AI coding sessions

Platform memories are weak background unless the user explicitly verifies them.

For Kiro, Specs describe intended requirements. QiJu records describe historical evidence.
If they conflict, inspect both and reconcile before editing.

## Typical Flow

Install once:

```bash
bash install.sh
```

Enable a project from inside Codex:

```bash
cd /path/to/project
qiju init --host codex
```

Later, from Kiro in the same project:

```bash
cd /path/to/project
qiju init --host kiro
```

Both hosts use the same `~/.qiju` store and the same project `.qiju` boot view, while
records remain attributable through the `agent` schema field.

## Uninstall Model

QiJu uninstall removes installation and generated host wiring, not memory records. Preview
the uninstall first:

```bash
qiju uninstall --dry-run
```

Then run it:

```bash
qiju uninstall
```

By default, uninstall removes the user-level install, generated QiJu wiring in the current
project, and generated QiJu wiring in ALL discovered QiJu-enabled projects under common
project roots. Pass `--no-scan-projects` to limit cleanup to the current project, or
`--user-only` for only the machine-level installation:

- remove the `qiju` CLI shim
- remove the installed engine copy at `~/.qiju/qiju`
- remove support templates under `~/.qiju/adapters` and `~/.qiju/agents`
- remove the runtime lock file `~/.qiju/.qiju.lock`
- remove generated global host integrations for selected hosts
- remove legacy Codex skills under `CODEX_HOME/skills/qiju-*` left by older installs that
  predated Codex's `.agents/skills/<name>/SKILL.md` contract

Use `--project-only` or `--project-root /path/to/project` for project-local wiring:

- remove generated Codex/Claude `qiju-log`, `qiju-search`, and `qiju-review` skills (and any legacy `CLAUDE.md` block or unified `/qiju` skill left by older installs)
- remove generated Kiro `qiju-log`, `qiju-search`, and `qiju-review` skills (`.kiro/skills/`); also purge any legacy `.kiro/agents/qiju.json`, `.kiro/skills/qiju/`, `.kiro/steering/qiju.md`, and `.kiro/prompts/qiju-agent-prompt.md` left by older installs
- remove generated Cursor `qiju-log`, `qiju-search`, and `qiju-review` skills; also purge the legacy `.cursor/rules/qiju.mdc` rule left by older installs
- preserve only `.qiju/short.jsonl` when local short records exist
- remove `.qiju/config.json`, temp entry files, and any legacy `.qiju/STATE.md` left by older installs
- remove `.qiju/` when no local short records exist

Uninstall does not delete `~/.qiju/long`, `~/.qiju/archive`, redaction logs, or
global long/archive records for any project.

To preview project discovery explicitly:

```bash
qiju uninstall --dry-run --scan-root /path/to/projects
```

## Open Validation Items

- Test Kiro skill-first behavior (IDE `qiju-log`/`qiju-search`/`qiju-review` skills and CLI agent registering them via `resources`) when global and local agents both exist.
- Test Claude/Codex skill discovery after the QiJu rename.
- Test clean-exit hooks per host.
- Test install after deleting the original checkout.
