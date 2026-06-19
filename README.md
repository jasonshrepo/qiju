<div align="center">
  <img src="assets/logo.svg" alt="QiJu" width="440">
</div>

# QiJu · 起居

**English** | [中文](README.zh.md)

**Local-first, lossless session record layer for AI coding agents.**

*QiJu (起居, pronounced “CHEE-joo”) takes its name from the court diarists of imperial
China — the officials who recorded what the ruler said, did, and decided, so there would
be a faithful record for those who came after.*

QiJu keeps a written history of your development sessions in your project, as plain files
you own. Any agent — Claude Code, Codex, Kiro, Cursor, or whatever comes next — can pick up
where the last one left off, instead of relying on memory that's locked inside one tool.

**QiJu is not memory — it's a record layer.** It records *what happened, who did it, where
the evidence is, and what should happen next*, so agent work becomes auditable and
handoffable instead of trapped in opaque, vendor-owned recall. Ordinary "memory" answers
*what the model remembers*; QiJu answers *why we know it, where the proof is, who produced
it, whether it was verified, and who continues next.*

> QiJu is the clerk of the agent world. It doesn't store the world itself — it records what
> agents did, where the evidence is, whether the result is trusted, and who should continue
> next.

<p>
  <a href="https://github.com/jasonshrepo/qiju/actions/workflows/ci.yml"><img src="https://github.com/jasonshrepo/qiju/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-17313C.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-216C83.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-475A60.svg" alt="Platform: macOS | Linux">
  <img src="https://img.shields.io/badge/status-developer%20preview-C8553D.svg" alt="Status: developer preview">
</p>

---

## Contents

- [Try it in 5 minutes](#try-it-in-5-minutes)
- [The name: QiJu (起居)](#the-name-qiju-起居)
- [Why QiJu](#why-qiju)
- [The idea](#the-idea)
- [What QiJu does](#what-qiju-does)
- [What QiJu is not](#what-qiju-is-not)
- [QiJu vs. session-sharing tools](#qiju-vs-session-sharing-tools)
- [Current status](#current-status)
- [Known limits](#known-limits)
- [Try it from source](#try-it-from-source)
- [Using QiJu](#using-qiju)
- [Design principles](#design-principles)
- [Solution architecture](#solution-architecture)
- [License](#license)

## The name: QiJu (起居)

QiJu (起居, pronounced *CHEE-joo*) takes its name from the **court diarists of imperial
China** — the *qiju lang*, officials entrusted with recording the ruler's words, actions,
and daily affairs. Day after day they kept the *Qijuzhu* (起居注, the "Diary of Activity and
Repose"), the firsthand record that later historians relied on to compile the veritable
records and the official histories. The diarist did not govern and did not decide — the
diarist kept a faithful, verifiable account, so that those who came after could know what
truly happened, and why.

That is exactly this project's role. Swap "ruler" for "agent" and the job description is
the same:

| The court diarist · 起居郎 | QiJu (起居) |
| --- | --- |
| Recorded the ruler's words and acts | Records the decisions and steps in an agent session |
| Did not rule in the ruler's place | Does not act in the agent's place |
| Preserved evidence for the historical record | Preserves a verifiable session record |
| Supplied material for those who later wrote history | Hands off context to the next agent |
| Kept formal archives | Stores plain JSONL / Markdown / Parquet you own |
| Chose what was worth recording | Captures intentionally — never silent background memory |

> The agent does the work. QiJu keeps the record.

## Try it in 5 minutes

The whole loop — install, wire it into an agent, save a record, and have the *next* agent
read it back:

```bash
# 1. Install from source (adds `qiju` to ~/.local/bin, engine to ~/.qiju/qiju)
git clone https://github.com/jasonshrepo/qiju.git
cd qiju && bash install.sh

# 2. Wire it into a real project (pick your host: claude | codex | kiro | cursor)
cd /path/to/your/project
qiju init --host claude
```

Then, **inside the agent**, take a note and hand it off:

```text
/qiju-log    what we decided and what should happen next
```

Open a *different* agent in the same project later, and ask it to pick up where you left off:

```text
/qiju-search    the last decision
```

That's it — the record is a plain file in `.qiju/` and `~/.qiju` that any agent can read.
The project `.qiju/` is developer-owned, cross-agent session memory — it travels with the
repo, not with a vendor. See [Using QiJu](#using-qiju) for the per-host commands
(`/qiju-log`, `/qiju-search`, `/qiju-review`) and [Try it from source](#try-it-from-source) for install
details.

## Why QiJu

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

QiJu fixes this by keeping project history where it belongs: **in your project, as plain
files you own.** The next agent reads the same written record of what happened — not a
guess, not a vendor's black box.

## The idea

Treat your agent like a secretary. At the end of a session — or any time something matters —
you tell it to write down what you did and what you want remembered. That note becomes a
record in your project. Next time you open the project, the agent reads those records first,
so it already knows the history and can pick up where you left off. Like a good clerk, it
records the moments that matter — what was decided, where the evidence is, what's next — not
the data itself.

QiJu began as a one-line `/log` skill: it appended a summary of the session to a `history.md`
file (a per-project copy and a global one), read back at the start of every session. That
worked — until the history grew too big to re-read every time. QiJu is that same idea,
structured so it scales: many small records instead of one growing file, a short summary to
read on start, and deterministic search to pull only what's relevant.

## What QiJu does

You direct the agent; it takes the notes:

1. **Capture** — you ask the agent to write down what you did and what's worth remembering.
   Record a whole session, or point at the specific things you want kept.
2. **Preserve** — the agent writes the note; QiJu stores it exactly and never re-summarizes
   or evicts it the way a context window does.
3. **Retrieve** — pull the relevant past records when you need them.
4. **Hand off** — the next agent or session reads those records first.
5. **Reason** — the model works from real notes you can see and trust, not memory it invented.

Nothing is logged silently in the background — **you decide what gets recorded.** The records
are just files in your repository and home directory: open them, read them, diff them in git,
edit or redact anything.

## What QiJu is not

| QiJu is not | In plain terms |
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
| A sharing / presentation surface (e.g. [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts)) | It doesn't publish a web page for a human to look at. It writes machine-readable records so the *next agent* can continue. See [QiJu vs. session-sharing tools](#qiju-vs-session-sharing-tools). |

## QiJu vs. session-sharing tools

Tools like **[Claude Code Artifacts](https://code.claude.com/docs/en/artifacts)** also "capture
what happened in a session," so it's worth being precise about the difference. They solve
opposite halves of the problem:

- **Artifacts is a *presentation* layer for humans.** It turns session output into a live,
  interactive web page at a private URL so a *teammate* can look at it — an annotated diff, a
  dashboard, options side by side.
- **QiJu is a *record* layer for agents.** It writes durable, machine-readable records so the
  *next agent* — in any tool — can verify the evidence and continue the work.

| | **QiJu (起居)** | **Claude Code Artifacts** |
|---|---|---|
| **Purpose** | Lossless session record → agent handoff & continuity | Turn session output into a shareable web page |
| **Primary consumer** | The next AI agent (and you, auditing) | Human reviewers / teammates |
| **Output** | Plain JSONL / Markdown / Parquet records | One self-contained HTML/Markdown page |
| **Where it lives** | Local — `.qiju/` + `~/.qiju`, files you own | Anthropic infra (claude.ai), private URL |
| **Persistence** | Permanent, tiered; never auto-evicted | Versioned page with an org retention policy |
| **Sharing** | Travels with the repo (git); cross-tool, cross-vendor | Within your org only; sign-in required |
| **Lock-in** | None — Claude Code, Codex, Kiro, Cursor | Anthropic-only; Team/Enterprise plan + claude.ai login |
| **Retrieval** | Deterministic keyword/tag/regex search | None — a page is viewed, not queried |
| **Cost** | Free, open source (Apache-2.0) | Paid plan, beta |

The two are **complementary, not competing**: publish an Artifact so a human can review the
work *now*, and run `/qiju-log` so the next agent can pick it up *later*. Artifact = the
meeting slide; QiJu = the court diary. One is shown and discarded; one is kept and read back.

## Current status

QiJu is a **source-first developer preview**. You install it from this repository; there is
no public package-manager release yet.

What works today, and is covered by the test suite (`uv run pytest`):

- Capturing session records (`qiju log`).
- Finding past records (`qiju search`, `qiju show`) and listing known projects (`qiju projects`).
- Tidy-up and long-term archiving of old records (`qiju maintain`).
- One-time normalization of project names in an existing store (`qiju migrate`).
- Removing secrets from records, including after the fact (`qiju redact`).
- Wiring QiJu into your agent of choice (`qiju init --host …`) and removing it cleanly
  (`qiju uninstall`) without ever deleting your records.

## Known limits

QiJu is deliberately small, and this is an early preview. Be aware that:

- **Source-first install only.** You install from this repo with `bash install.sh`. There is
  no `pip install qiju`, `brew install qiju`, or `npm install -g qiju` yet.
- **Deterministic retrieval, not semantic search.** Search matches exact keywords, tags, and
  regex — there are no embeddings, vector similarity, or relevance ranking. The model judges
  relevance after QiJu returns candidates.
- **Intentional capture only.** Nothing is logged silently in the background. You (or the
  agent, on your instruction) decide what gets recorded; QiJu does not auto-ingest
  transcripts, prompts, or tool calls.
- **macOS and Linux only.** Windows is not supported or tested.
- **Developer preview.** Record formats, the CLI surface, and host wiring may still change
  between versions; expect rough edges and please file issues.

## Try it from source

> Source-first only for now. There is no `npm install -g qiju`, `brew install qiju`, or
> `pip install qiju` yet.

```bash
git clone https://github.com/jasonshrepo/qiju.git
cd qiju

# Installs the `qiju` command (to ~/.local/bin) and an engine copy (to ~/.qiju/qiju)
bash install.sh

# Optional: macOS scheduled maintenance
bash install.sh --install-launchd
```

Make sure `~/.local/bin` is on your `PATH`, then check it's working:

```bash
qiju --help
```

Records are stored under `~/.qiju` by default. Override with `export QIJU_HOME=/path/to/store`.

**Working on QiJu itself:**

```bash
uv sync          # install dependencies (Python >=3.11)
uv run pytest    # run the test suite
```

## Using QiJu

### 1. Connect a project to your agent (one-time setup)

Run this yourself in a terminal, once per project:

```bash
cd /path/to/project
qiju init --host claude        # or: codex | kiro | cursor
qiju init --host claude --global   # optional user-level defaults
```

This wires the `qiju` command into your agent. From then on, you work through the agent — you
don't run the raw CLI by hand.

### 2. Day to day, you talk to the agent

QiJu gives you three explicit skills:

```text
/qiju-log                       save a record of this session
/qiju-log <what to record>      record something specific you want kept
/qiju-search <query>            find past records
/qiju-search what's pending     roll up open next steps as a checklist
/qiju-review                    review recent records for lessons and prompt improvements
```

How you trigger them depends on the host:

| Host | How you call QiJu |
|---|---|
| **Claude Code** (CLI & desktop) | `/qiju-log`, `/qiju-search`, `/qiju-review` — or just ask in natural language; the skill descriptions trigger discovery |
| **Kiro** (CLI & IDE) | `/qiju-log`, `/qiju-search`, `/qiju-review` as slash commands, backed by the matching skills. In the **IDE** you can also just ask in natural language — "search QiJu for …", "save a QiJu record" — and the skill picks it up. |
| **Cursor** (CLI & IDE) | `/qiju-log`, `/qiju-search`, `/qiju-review` from `.cursor/skills/` — or natural language |
| **Codex** (CLI & desktop) | `$qiju-log`, `$qiju-search`, `$qiju-review` — or natural language |

You're the editor; the agent is the note-taker. When you log, the agent summarizes the
session (or the thing you pointed at) into a structured record and saves it — you decide what
goes in. At the start of the next session, the agent reads the project summary and the
relevant records back, so it already knows the history. You always just talk to the agent;
the agent calls the `qiju` CLI.

### Direct CLI (for scripts, or to see what the agent runs)

The agent ultimately runs the `qiju` CLI, and you can too — for automation or to inspect the
store directly:

```bash
# Save a record (the agent builds the JSON; you can also write it yourself or pipe via stdin)
qiju log --source manual --agent claude --project my-project --body record.json

# Find records — two-phase: search lists candidate <uuid>:N ids, show hydrates one
qiju search --scope current_project --query "auth cookie"
qiju search --scope all --tags security --since 2026-01-01
qiju show '<session-id>:1'                         # pass the id exactly as search prints it (the ':N' suffix is required)
qiju projects                                     # list known project slugs

# Maintenance, redaction, and removal (records are never deleted by uninstall)
qiju maintain --dry-run
qiju redact --value "secret-value" --reason "leaked in session"
qiju migrate --dry-run                            # preview project-name normalization (one-time upgrade step)

# Remove the integration — records are always preserved
qiju uninstall --dry-run                          # preview everything that would be removed
qiju uninstall --hosts kiro                        # remove just one host (claude|kiro|codex|cursor)
qiju uninstall --hosts kiro,cursor --project-only  # one or more hosts, project-local files only
qiju uninstall --no-scan-projects                  # clean only the current project
qiju uninstall --user-only                         # only user-level install + global host wiring
```

By default `uninstall` cleans ALL discovered QiJu-enabled projects under common project
roots (use `--no-scan-projects` to limit it to the current project). It scopes by **host**
(`--hosts all` or a comma list) and by **location** (`--project-only`, `--user-only`, or
both when neither is given), and also removes the runtime lock file `~/.qiju/.qiju.lock`.
Your `long` and `short` records are never deleted — only the integration files are.

Records anchor to your project root even if the agent runs `qiju log` from a subfolder — see
[Solution architecture](#solution-architecture) for how that resolution works.

## Design principles

- **A record layer, not memory** — QiJu captures what happened, who did it, the evidence, and
  the handoff, so work is auditable, verifiable, and recoverable — not just "remembered."
- **Local-first by default** — records live in your repo and `~/.qiju`, not a vendor service.
- **You direct what's recorded** — the agent is your secretary; capture is intentional, never
  silent background memory.
- **Lossless after capture** — once the agent writes a record, QiJu keeps it verbatim; it
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

This section is the technical deep dive. The sections above are enough to use QiJu; read on
if you want to understand how it works or extend it.

### Storage tiers

Every record is written to a hot tier and a durable tier on each `log`, then aged into an
archive tier by `qiju maintain`. Reads merge all three and deduplicate by `id`.

| Tier | Location | Retention |
|---|---|---|
| **short** (hot) | `<project>/.qiju/short.jsonl` | 14-day rolling window, project-local |
| **long** (durable) | `~/.qiju/long/<project>.jsonl` | All records, shared store |
| **archive** | `~/.qiju/archive/project=<name>/month=<YYYY-MM>/entries.parquet` | Aged records, DuckDB Parquet |

A local init creates:

```text
<project>/.qiju/
├── short.jsonl     # hot tier: 14-day rolling window
└── config.json     # init marker + canonical project slug

~/.qiju/
├── long/<project>.jsonl                                   # durable tier: all records
├── archive/project=<name>/month=<YYYY-MM>/entries.parquet # aged records (DuckDB Parquet)
└── redaction_log.jsonl
```

`qiju maintain` rotates the 14-day hot window and archives durable records older than ~92 days
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
  "search_terms": ["project_root", "QIJU_PROJECT_ROOT"],
  "next_steps": ["sync to release", "run smoke matrix"],
  "redactions": [],
  "body_md": "Full human-readable narrative of what happened..."
}
```

Valid `source` values are `manual` and `agent`. The `id` is
`{session-uuid}:{seq}`, where the session UUID comes from the first set of
`QIJU_SESSION_ID` / `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` / `KIRO_SESSION_ID`, and `seq`
increments per session.

### Deterministic retrieval

Retrieval is two-phase. **Phase 1 — `qiju search`** identifies candidates: it loads all
tiers for the requested scope, applies structured filters (source, agent, tags, time range),
then does an exact keyword or regex scan over `title + body_md + tags + search_terms +
next_steps`. Keyword matching is OR-based per term. Results are sorted by timestamp, newest
first, and printed as `{session-uuid}:{seq}` ids. There is no embedding model and no
relevance score — search identifies candidates, and the model decides what matters.

**Phase 2 — `qiju show '<uuid>:N'`** hydrates one record's full body by its exact id. Pass
the id exactly as `qiju search` prints it, including the `:N` suffix; a bare UUID returns
`record not found` with a hint to add the suffix (the UUID alone denotes a whole session,
not a single record).

### Project-root resolution

`qiju log` resolves the project root by precedence:

1. `QIJU_PROJECT_ROOT` environment variable.
2. The nearest ancestor directory containing the `.qiju/config.json` init marker (written
   only by `qiju init`, so a stray `.qiju/` data dir in a subfolder can't hijack resolution).
3. The git repository root (`git rev-parse --show-toplevel`).
4. The current working directory, as a last resort.

The project slug is read from the init marker, so records stay anchored to the right project
even when an agent runs `qiju log` from a subdirectory, and the slug is stable across
directory renames. Project names are normalized to one canonical **lowercase** slug at every
entry point (log, search, storage filenames), so `MyProject` and `myproject` are the same
project and a casing slip can't fork the history. If none of the above identifies a root and
no `--project` is given, `qiju log` aborts rather than create a stray identity.

### Redaction

Redaction runs at write time before a record is persisted: regex rules from a configurable
ruleset, followed by Shannon-entropy detection to catch high-entropy tokens (e.g. keys), with
an allowlist to bypass known-safe values. `qiju redact --value …` performs retroactive
redaction, rewriting every JSONL and Parquet tier to replace a literal value and appending an
audit event to `~/.qiju/redaction_log.jsonl`.

> **Redaction is best-effort.** The regex rules and entropy check catch common credentials,
> secrets, and regex-detectable PII (emails, phone numbers, API keys, SSNs, etc.), but they
> are **not** a guarantee. They will miss free-form or ambiguous personal data — especially
> names, physical addresses, and context-dependent identifiers. The first line of defence is
> not writing secrets or PII into records in the first place.
>
> If you need strict PII detection, you can opt in to an external solution as a pre-processing
> step before logging:
>
> - **Microsoft Presidio** — runs locally; keeps text on your machine and preserves QiJu's
>   local-first guarantee.
> - **Cloud DLP/PII APIs** (AWS, Google, Azure) — more capable, but they send your record text
>   **off the local machine** to a third-party service. That directly conflicts with QiJu's
>   local-first promise; only use them if your threat model accepts that tradeoff.
>
> QiJu does not bundle Presidio or any cloud SDK — these are documentation suggestions only,
> not dependencies.

### Host wiring

`qiju init --host <host>` wires QiJu into a project (or user-global location) per host:
Claude, Codex, Kiro, and Cursor each get three skills — `qiju-log`, `qiju-search`, and
`qiju-review` — under the provider's skills directory (`.claude/skills/`,
`.agents/skills/`, `.kiro/skills/`, `.cursor/skills/`). The skills only tell the agent how
to call the `qiju` CLI — records are always written by the CLI to the tiers above, never by
the skill itself.

QiJu ships only the portable Agent Skills shape: `skills/<skill-name>/SKILL.md`, plus
portable optional folders such as `scripts/`, `references/`, or `assets/` if a future skill
needs them. It does not ship provider-specific metadata files. If you want provider-specific
behavior, add it manually to your own installed copy after `qiju init`: for example, Codex
users can add `agents/openai.yaml` for Codex app UI metadata or invocation policy, Cursor
users can add Cursor-only frontmatter such as `paths` or `disable-model-invocation`, Kiro
users can create their own `.kiro/agents/qiju.json` if they want a named Kiro CLI agent,
and Claude users can add provider-supported optional fields where the docs allow them. See
the provider docs for details: [Codex](https://developers.openai.com/codex/skills),
[Kiro](https://kiro.dev/docs/skills/),
[Claude](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), and
[Cursor](https://cursor.com/docs/skills).

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Jason Shen.
