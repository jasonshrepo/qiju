<div align="center">
  <img src="assets/logo.svg" alt="Kedu" width="440">
</div>

# Kedu · 刻牍

**English** | [中文](README.zh.md)

**Local-first, lossless session record layer for AI coding agents.**

*Kedu (刻牍, pronounced “Kay-Doo”) means “to inscribe records” — carving down what happened
so it lasts.*

Kedu keeps a written history of your development sessions in your project, as plain files
you own. Any agent — Claude Code, Codex, Kiro, Cursor, or whatever comes next — can pick up
where the last one left off, instead of relying on memory that's locked inside one tool.

**Kedu is not memory — it's a record layer.** It records *what happened, who did it, where
the evidence is, and what should happen next*, so agent work becomes auditable and
handoffable instead of trapped in opaque, vendor-owned recall. Ordinary "memory" answers
*what the model remembers*; Kedu answers *why we know it, where the proof is, who produced
it, whether it was verified, and who continues next.*

> Kedu is the clerk of the agent world. It doesn't store the world itself — it records what
> agents did, where the evidence is, whether the result is trusted, and who should continue
> next.

<p>
  <a href="https://github.com/jasonshrepo/kedu/actions/workflows/ci.yml"><img src="https://github.com/jasonshrepo/kedu/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-17313C.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-216C83.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-475A60.svg" alt="Platform: macOS | Linux">
  <img src="https://img.shields.io/badge/status-developer%20preview-C8553D.svg" alt="Status: developer preview">
</p>

---

## Contents

- [Try it in 5 minutes](#try-it-in-5-minutes)
- [Why Kedu](#why-kedu)
- [The idea](#the-idea)
- [What Kedu does](#what-kedu-does)
- [What Kedu is not](#what-kedu-is-not)
- [Current status](#current-status)
- [Known limits](#known-limits)
- [Try it from source](#try-it-from-source)
- [Using Kedu](#using-kedu)
- [Design principles](#design-principles)
- [Solution architecture](#solution-architecture)
- [License](#license)

## Try it in 5 minutes

The whole loop — install, wire it into an agent, save a record, and have the *next* agent
read it back:

```bash
# 1. Install from source (adds `kedu` to ~/.local/bin, engine to ~/.kedu/kedu)
git clone https://github.com/jasonshrepo/kedu.git
cd kedu && bash install.sh

# 2. Wire it into a real project (pick your host: claude | codex | kiro | cursor)
cd /path/to/your/project
kedu init --host claude
```

Then, **inside the agent**, take a note and hand it off:

```text
/kedu-log    what we decided and what should happen next
```

Open a *different* agent in the same project later, and ask it to pick up where you left off:

```text
/kedu-search    the last decision
```

That's it — the record is a plain file in `.kedu/` and `~/.kedu` that any agent can read.
The project `.kedu/` is developer-owned, cross-agent session memory — it travels with the
repo, not with a vendor. See [Using Kedu](#using-kedu) for the per-host commands
(`/kedu-log`, `/kedu-search`) and [Try it from source](#try-it-from-source) for install
details.

## Why Kedu

Getting an AI coding agent genuinely useful on a real project takes effort. You explain the
architecture, the decisions, the dead ends, what's half-finished. Then the session ends —
and all of that understanding evaporates. Next time, you start over.

Today that hard-won context gets trapped:

- **It dies with the thread.** Close the chat or hit the context limit, and the shared
  understanding is gone.
- **It doesn't move between tools.** Switch from Claude Code to Cursor — or hand off to a
  teammate — and the new agent knows nothing about your project.
- **It's locked to a vendor.** Platform "memory" lives on someone else's servers. You can't
  read it, edit it, or take it with you.
- **It gets summarized away.** Long sessions are compacted into lossy recaps, and the detail
  you actually needed is the first thing dropped.

Kedu fixes this by keeping project history where it belongs: **in your project, as plain
files you own.** The next agent reads the same written record of what happened — not a
guess, not a vendor's black box.

## The idea

Treat your agent like a secretary. At the end of a session — or any time something matters —
you tell it to write down what you did and what you want remembered. That note becomes a
record in your project. Next time you open the project, the agent reads those records first,
so it already knows the history and can pick up where you left off. Like a good clerk, it
records the moments that matter — what was decided, where the evidence is, what's next — not
the data itself.

Kedu began as a one-line `/log` skill: it appended a summary of the session to a `history.md`
file (a per-project copy and a global one), read back at the start of every session. That
worked — until the history grew too big to re-read every time. Kedu is that same idea,
structured so it scales: many small records instead of one growing file, a short summary to
read on start, and deterministic search to pull only what's relevant.

## What Kedu does

You direct the agent; it takes the notes:

1. **Capture** — you ask the agent to write down what you did and what's worth remembering.
   Record a whole session, or point at the specific things you want kept.
2. **Preserve** — the agent writes the note; Kedu stores it exactly and never re-summarizes
   or evicts it the way a context window does.
3. **Retrieve** — pull the relevant past records when you need them.
4. **Hand off** — the next agent or session reads those records first.
5. **Reason** — the model works from real notes you can see and trust, not memory it invented.

Nothing is logged silently in the background — **you decide what gets recorded.** The records
are just files in your repository and home directory: open them, read them, diff them in git,
edit or redact anything.

## What Kedu is not

| Kedu is not | In plain terms |
|---|---|
| Memory | It doesn't make the model "remember more." It records what was done and where the proof is, so the next agent can verify and continue. |
| A database | It doesn't hold your bulk data — posts, comments, tables, files. It records *where* that data lives (paths, counts, hashes), not the data itself. |
| Vector memory / RAG | No embeddings, no fuzzy similarity guessing. It finds records by exact filters and keywords. |
| A search engine | It surfaces likely-relevant records; the model decides what actually matters. There's no ranking score. |
| A crawler / connector | It doesn't fetch from the web or platform APIs. It records *that* a fetch happened and points at the output. |
| A dashboard | It doesn't render or visualize. It's the underlying record other tools can read. |
| Chat history | Not a transcript dump. Intentional, structured records of decisions, evidence, and next steps. |
| An agent framework | It doesn't run or steer agents. It records sessions and hands context to whatever agent you use. |
| Platform memory | Your records are local files you own — not memory held on a vendor's servers. |

## Current status

Kedu is a **source-first developer preview**. You install it from this repository; there is
no public package-manager release yet.

What works today, and is covered by the test suite (`uv run pytest`):

- Capturing session records (`kedu log`).
- Finding past records (`kedu search`, `kedu show`).
- Tidy-up and long-term archiving of old records (`kedu maintain`).
- Removing secrets from records, including after the fact (`kedu redact`).
- Wiring Kedu into your agent of choice (`kedu init --host …`) and removing it cleanly
  (`kedu uninstall`) without ever deleting your records.

## Known limits

Kedu is deliberately small, and this is an early preview. Be aware that:

- **Source-first install only.** You install from this repo with `bash install.sh`. There is
  no `pip install kedu`, `brew install kedu`, or `npm install -g kedu` yet.
- **Deterministic retrieval, not semantic search.** Search matches exact keywords, tags, and
  regex — there are no embeddings, vector similarity, or relevance ranking. The model judges
  relevance after Kedu returns candidates.
- **Intentional capture only.** Nothing is logged silently in the background. You (or the
  agent, on your instruction) decide what gets recorded; Kedu does not auto-ingest
  transcripts, prompts, or tool calls.
- **macOS and Linux only.** Windows is not supported or tested.
- **Developer preview.** Record formats, the CLI surface, and host wiring may still change
  between versions; expect rough edges and please file issues.

## Try it from source

> Source-first only for now. There is no `npm install -g kedu`, `brew install kedu`, or
> `pip install kedu` yet.

```bash
git clone https://github.com/jasonshrepo/kedu.git
cd kedu

# Installs the `kedu` command (to ~/.local/bin) and an engine copy (to ~/.kedu/kedu)
bash install.sh

# Optional: macOS scheduled maintenance
bash install.sh --install-launchd
```

Make sure `~/.local/bin` is on your `PATH`, then check it's working:

```bash
kedu --help
```

Records are stored under `~/.kedu` by default. Override with `export KEDU_HOME=/path/to/store`.

**Working on Kedu itself:**

```bash
uv sync          # install dependencies (Python >=3.11)
uv run pytest    # run the test suite
```

## Using Kedu

### 1. Connect a project to your agent (one-time setup)

Run this yourself in a terminal, once per project:

```bash
cd /path/to/project
kedu init --host claude        # or: codex | kiro | cursor
kedu init --host claude --global   # optional user-level defaults
```

This wires the `kedu` command into your agent. From then on, you work through the agent — you
don't run the raw CLI by hand.

### 2. Day to day, you talk to the agent

Kedu gives you two explicit skills:

```text
/kedu-log                       save a record of this session
/kedu-log <what to record>      record something specific you want kept
/kedu-search <query>            find past records
/kedu-search what's pending     roll up open next steps as a checklist
```

How you trigger them depends on the host:

| Host | How you call Kedu |
|---|---|
| **Claude Code** (CLI & desktop) | `/kedu-log`, `/kedu-search` — or just ask in natural language; the skill descriptions trigger discovery |
| **Kiro** (CLI & IDE) | `/kedu-log`, `/kedu-search` as slash commands, backed by the matching skills. In the **IDE** you can also just ask in natural language — "search Kedu for …", "save a Kedu record" — and the skill picks it up. |
| **Cursor** (CLI; IDE unverified) | natural-language asks, guided by the `.cursor/rules/kedu.mdc` rule |
| **Codex** (CLI & desktop) | `$kedu-log`, `$kedu-search` — or natural language |

You're the editor; the agent is the note-taker. When you log, the agent summarizes the
session (or the thing you pointed at) into a structured record and saves it — you decide what
goes in. At the start of the next session, the agent reads the project summary and the
relevant records back, so it already knows the history. You always just talk to the agent;
the agent calls the `kedu` CLI.

### Direct CLI (for scripts, or to see what the agent runs)

The agent ultimately runs the `kedu` CLI, and you can too — for automation or to inspect the
store directly:

```bash
# Save a record (the agent builds the JSON; you can also write it yourself or pipe via stdin)
kedu log --source manual --agent claude --project my-project --body record.json

# Find records
kedu search --scope current_project --query "auth cookie"
kedu search --scope all --tags security --since 2026-01-01
kedu show '<session-id>:1'

# Maintenance, redaction, and removal (records are never deleted by uninstall)
kedu maintain --dry-run
kedu redact --value "secret-value" --reason "leaked in session"

# Remove the integration — records are always preserved
kedu uninstall --dry-run                          # preview everything that would be removed
kedu uninstall --hosts kiro                        # remove just one host (claude|kiro|codex|cursor)
kedu uninstall --hosts kiro,cursor --project-only  # one or more hosts, project-local files only
kedu uninstall --no-scan-projects                  # clean only the current project
kedu uninstall --user-only                         # only user-level install + global host wiring
```

By default `uninstall` cleans ALL discovered Kedu-enabled projects under common project
roots (use `--no-scan-projects` to limit it to the current project). It scopes by **host**
(`--hosts all` or a comma list) and by **location** (`--project-only`, `--user-only`, or
both when neither is given), and also removes the runtime lock file `~/.kedu/.kedu.lock`.
Your `long` and `short` records are never deleted — only the integration files are.

Records anchor to your project root even if the agent runs `kedu log` from a subfolder — see
[Solution architecture](#solution-architecture) for how that resolution works.

## Design principles

- **A record layer, not memory** — Kedu captures what happened, who did it, the evidence, and
  the handoff, so work is auditable, verifiable, and recoverable — not just "remembered."
- **Local-first by default** — records live in your repo and `~/.kedu`, not a vendor service.
- **You direct what's recorded** — the agent is your secretary; capture is intentional, never
  silent background memory.
- **Lossless after capture** — once the agent writes a record, Kedu keeps it verbatim; it
  never re-summarizes, compacts, or evicts it.
- **Records you can see and trust** — explicit notes you and the agent write and can edit, not
  invisible vendor memory.
- **Deterministic retrieval before model reasoning** — exact filters find candidates; the
  model judges relevance.
- **Inspectable files over black-box recall** — plain JSON and Markdown you can read, diff,
  and redact.
- **Developer-owned history over platform-owned memory** — your files, your store, your
  control.

---

## Solution architecture

This section is the technical deep dive. The sections above are enough to use Kedu; read on
if you want to understand how it works or extend it.

### Storage tiers

Every record is written to a hot tier and a durable tier on each `log`, then aged into an
archive tier by `kedu maintain`. Reads merge all three and deduplicate by `id`.

| Tier | Location | Retention |
|---|---|---|
| **short** (hot) | `<project>/.kedu/short.jsonl` | 14-day rolling window, project-local |
| **long** (durable) | `~/.kedu/long/<project>.jsonl` | All records, shared store |
| **archive** | `~/.kedu/archive/project=<name>/month=<YYYY-MM>/entries.parquet` | Aged records, DuckDB Parquet |

A local init creates:

```text
<project>/.kedu/
├── short.jsonl     # hot tier: 14-day rolling window
└── config.json     # init marker + canonical project slug

~/.kedu/
├── long/<project>.jsonl                                   # durable tier: all records
├── archive/project=<name>/month=<YYYY-MM>/entries.parquet # aged records (DuckDB Parquet)
└── redaction_log.jsonl
```

`kedu maintain` rotates the 14-day hot window and archives durable records older than ~92 days
(forced at 31 days if the long file exceeds 50 MB) into Parquet via DuckDB.

### Record schema

Each record is a JSON object (schema version 2):

```json
{
  "schema_version": 2,
  "id": "<session-uuid>:<seq>",
  "ts": "2026-06-03T00:28:54+10:00",
  "project": "my-project",
  "agent": "claude",
  "source": "manual",
  "title": "Fixed project-root resolution for non-git repos",
  "tags": ["bugfix", "paths"],
  "search_terms": ["project_root", "KEDU_PROJECT_ROOT"],
  "next_steps": ["sync to release", "run smoke matrix"],
  "redactions": [],
  "body_md": "Full human-readable narrative of what happened..."
}
```

Valid `source` values are `manual` and `agent`. The `id` is
`{session-uuid}:{seq}`, where the session UUID comes from the first set of
`KEDU_SESSION_ID` / `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` / `KIRO_SESSION_ID`, and `seq`
increments per session.

### Deterministic retrieval

`kedu search` loads all tiers for the requested scope, applies structured filters (source,
agent, tags, time range), then does an exact keyword or regex scan over
`title + body_md + tags + search_terms + next_steps`. Keyword matching is OR-based per term.
Results are sorted by timestamp, newest first. There is no embedding model and no relevance
score — search identifies candidates, and the model decides what matters.

### Project-root resolution

`kedu log` resolves the project root by precedence:

1. `KEDU_PROJECT_ROOT` environment variable.
2. The nearest ancestor directory containing the `.kedu/config.json` init marker (written
   only by `kedu init`, so a stray `.kedu/` data dir in a subfolder can't hijack resolution).
3. The git repository root (`git rev-parse --show-toplevel`).
4. The current working directory, as a last resort.

The project slug is read from the init marker, so records stay anchored to the right project
even when an agent runs `kedu log` from a subdirectory, and the slug is stable across
directory renames. If none of the above identifies a root and no `--project` is given,
`kedu log` aborts rather than create a stray identity.

### Redaction

Redaction runs at write time before a record is persisted: regex rules from a configurable
ruleset, followed by Shannon-entropy detection to catch high-entropy tokens (e.g. keys), with
an allowlist to bypass known-safe values. `kedu redact --value …` performs retroactive
redaction, rewriting every JSONL and Parquet tier to replace a literal value and appending an
audit event to `~/.kedu/redaction_log.jsonl`.

> **Redaction is best-effort.** The regex rules and entropy check catch common credentials,
> secrets, and regex-detectable PII (emails, phone numbers, API keys, SSNs, etc.), but they
> are **not** a guarantee. They will miss free-form or ambiguous personal data — especially
> names, physical addresses, and context-dependent identifiers. The first line of defence is
> not writing secrets or PII into records in the first place.
>
> If you need strict PII detection, you can opt in to an external solution as a pre-processing
> step before logging:
>
> - **Microsoft Presidio** — runs locally; keeps text on your machine and preserves Kedu's
>   local-first guarantee.
> - **Cloud DLP/PII APIs** (AWS, Google, Azure) — more capable, but they send your record text
>   **off the local machine** to a third-party service. That directly conflicts with Kedu's
>   local-first promise; only use them if your threat model accepts that tradeoff.
>
> Kedu does not bundle Presidio or any cloud SDK — these are documentation suggestions only,
> not dependencies.

### Host wiring

`kedu init --host <host>` wires Kedu into a project (or user-global location) per host:
Claude, Codex, and Kiro each get two skills — `kedu-log` and `kedu-search` — under their
skills directory (`.claude/skills/`, `.agents/skills/`, `.kiro/skills/`); Kiro also gets a
CLI agent config under `.kiro/`. Cursor gets a single rule under `.cursor/rules/` (the
Cursor CLI is verified; the Cursor IDE is not). The skills only tell the agent how to call
the `kedu` CLI — records are always written by the CLI to the tiers above, never by the
skill or rule itself.

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Jason Shen.
