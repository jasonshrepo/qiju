# Install And Host Init Model

Kedu has two separate setup steps.

## 1. Install Kedu

Run once per machine:

```bash
bash install.sh
```

This installs:

- `kedu` CLI
- shared store at `~/.kedu`
- installed engine copy at `~/.kedu/kedu`
- shared support templates under `~/.kedu/agents`

This step does not enable Kedu inside a specific project. The `kedu` command refers to the
installed engine copy, so the downloaded installer checkout can be deleted after
installation.

## 2. Enable A Project Host

Project-local setup is the first/default step:

```bash
cd /path/to/project
kedu init --host codex
```

Supported hosts:

- `claude`
- `kiro`
- `codex`
- `cursor`

Optional user/global defaults can be added later:

```bash
kedu init --host codex --global
```

When called from inside a supported agent, `--host` may be omitted if Kedu can detect the
host from the environment or project markers:

```bash
kedu init
```

## Scope Semantics

Local init means "enable Kedu for this host in the current project." It creates:

```text
<project>/.kedu/
├── short.jsonl
└── config.json
```

It also writes project-local host integration. Kedu is skill-first: each agent gets two
explicit skills — `kedu-log` (save a record) and `kedu-search` (retrieve history) — with no
always-on `CLAUDE.md` block and no `STATE.md`. The skills carry trigger-tuned descriptions
so the agent auto-discovers them; they mandate nothing on init.

- Claude: writes `.claude/skills/kedu-log/SKILL.md` and `.claude/skills/kedu-search/SKILL.md`. No `CLAUDE.md` block.
- Codex: writes `.agents/skills/kedu-log/SKILL.md` and `.agents/skills/kedu-search/SKILL.md`.
- Kiro: writes a Kiro CLI agent at `.kiro/agents/kedu.json` plus `.kiro/skills/kedu-log/SKILL.md` and `.kiro/skills/kedu-search/SKILL.md` (skill-first; no steering file and no saved prompt). The agent config registers both skills through its `resources` glob.
- Cursor: writes one `.cursor/rules/kedu.mdc` containing both the log and search guidance. **Cursor IDE is unverified — only the Cursor CLI is tested.**

In Claude Code, Codex, and Kiro, invoke the skills directly:

```text
/kedu-log
/kedu-search <query>
```

If the project is a git repo, `.kedu/` is added to `.git/info/exclude`, not `.gitignore`.

Global init means "install optional user-level defaults for this host." It is not required
for a project to use Kedu.

For Kiro CLI, local/global init makes a selectable `kedu` agent. Use:

```bash
kiro-cli --agent kedu chat
```

If you want Kiro CLI to use that agent by default, run this explicitly:

```bash
kiro-cli agent set-default kedu
```

Kiro does not use automatic Kedu hooks. Log explicitly before ending work, and write
temporary entry JSON inside the workspace, such as `.kedu/kedu-entry.json`, not `/tmp`.

## Shared Store Rule

All agents share one store:

```text
~/.kedu/
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

Kedu records are verified session handoff records and project history. Generated host
instructions should treat Kedu as the source of truth for:

- previous session progress
- active implementation decisions
- unresolved bugs
- previous attempts
- next steps
- what actually happened in prior AI coding sessions

Platform memories are weak background unless the user explicitly verifies them.

For Kiro, Specs describe intended requirements. Kedu records describe historical evidence.
If they conflict, inspect both and reconcile before editing.

## Typical Flow

Install once:

```bash
bash install.sh
```

Enable a project from inside Codex:

```bash
cd /path/to/project
kedu init --host codex
```

Later, from Kiro in the same project:

```bash
cd /path/to/project
kedu init --host kiro
```

Both hosts use the same `~/.kedu` store and the same project `.kedu` boot view, while
records remain attributable through the `agent` schema field.

## Uninstall Model

Kedu uninstall removes installation and generated host wiring, not memory records. Preview
the uninstall first:

```bash
kedu uninstall --dry-run
```

Then run it:

```bash
kedu uninstall
```

By default, uninstall removes the user-level install, generated Kedu wiring in the current
project, and generated Kedu wiring in ALL discovered Kedu-enabled projects under common
project roots. Pass `--no-scan-projects` to limit cleanup to the current project, or
`--user-only` for only the machine-level installation:

- remove the `kedu` CLI shim
- remove the installed engine copy at `~/.kedu/kedu`
- remove support templates under `~/.kedu/adapters` and `~/.kedu/agents`
- remove the runtime lock file `~/.kedu/.kedu.lock`
- remove generated global host integrations for selected hosts

Use `--project-only` or `--project-root /path/to/project` for project-local wiring:

- remove generated Codex/Claude `kedu-log` and `kedu-search` skills (and any legacy `CLAUDE.md` block or unified `/kedu` skill left by older installs)
- remove the generated Kiro CLI agent (`.kiro/agents/kedu.json`) and the `kedu-log`/`kedu-search` skills (`.kiro/skills/`); also purge any legacy `.kiro/skills/kedu/`, `.kiro/steering/kedu.md`, and `.kiro/prompts/kedu-agent-prompt.md` left by older installs
- remove generated Cursor rules
- preserve only `.kedu/short.jsonl` when local short records exist
- remove `.kedu/config.json`, temp entry files, and any legacy `.kedu/STATE.md` left by older installs
- remove `.kedu/` when no local short records exist

Uninstall does not delete `~/.kedu/long`, `~/.kedu/archive`, redaction logs, or
global long/archive records for any project.

To preview project discovery explicitly:

```bash
kedu uninstall --dry-run --scan-root /path/to/projects
```

## Open Validation Items

- Test Kiro skill-first behavior (IDE `kedu-log`/`kedu-search` skills and CLI agent registering them via `resources`) when global and local agents both exist.
- Test Claude/Codex skill discovery after the Kedu rename.
- Test clean-exit hooks per host.
- Test install after deleting the original checkout.
