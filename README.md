<div align="center">
  <img src="assets/logo.svg" alt="Kedu" width="440">
</div>

# Kedu

**Local-first, lossless session records for AI coding agents.**

Kedu preserves verified development session records so Claude Code, Codex, Cursor, Kiro,
and future agents can resume work from developer-owned project history instead of relying
on platform-specific memory.

It is a durable handoff layer: capture what happened, preserve it locally, retrieve
candidate records deterministically, and let the model reason over verified context.

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-17313C.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-216C83.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-475A60.svg" alt="Platform: macOS | Linux">
  <img src="https://img.shields.io/badge/status-developer%20preview-C8553D.svg" alt="Status: developer preview">
</p>

---

## Contents

- [Current status](#current-status)
- [Why Kedu](#why-kedu)
- [What Kedu is](#what-kedu-is)
- [What Kedu is not](#what-kedu-is-not)
- [Try it from source](#try-it-from-source)
- [Workflow](#workflow)
- [Record structure](#record-structure)
- [Design principles](#design-principles)
- [Roadmap](#roadmap)
- [License](#license)

## Current status

Kedu is **source-first / developer preview**. You install it from this repository; there is
no public package-manager distribution yet (see [Roadmap](#roadmap)).

What exists in the repo today, verified and tested (`uv run pytest`, 79 tests):

- A stable local record format — JSONL (hot + durable tiers) plus DuckDB Parquet archive.
- A capture workflow — `kedu log` (validate → redact → append → rebuild state).
- Deterministic retrieval — `kedu search` and `kedu show`.
- A derived project boot view — `kedu state` / `kedu rebuild-state` writing `.kedu/STATE.md`.
- Write-time and retroactive redaction — `kedu redact` (regex rules + entropy detection).
- Archival tiering — `kedu maintain` rotates the hot window and ages records to Parquet.
- Host wiring — `kedu init --host {claude,codex,cursor,kiro}` and `kedu uninstall`.
- A source-first installer — `install.sh` (with optional macOS scheduled maintenance).

## Why Kedu

AI coding agents are powerful, but continuity is fragile. Project context tends to get
trapped inside:

- one chat thread,
- one IDE,
- one model vendor,
- one platform-specific memory system,
- or a lossy summary.

When the thread ends, the agent restarts, or you switch tools, that context is gone or
degraded. Kedu keeps project history **local, inspectable, and developer-owned** — plain
files in your repo and home directory that any agent can read.

## What Kedu is

A durable handoff layer between sessions and between agents:

1. **Capture** what happened as a structured record.
2. **Preserve** verified records locally, losslessly.
3. **Retrieve** candidate records deterministically (structured filters + exact scan).
4. **Hand off** that verified context to the next agent or session.
5. **Reason** — the model decides relevance over real records, not invented memory.

## What Kedu is not

| Kedu is not | Because |
|---|---|
| Vector memory / RAG | No embeddings or similarity ranking. Retrieval is exact structured filtering plus keyword/regex scan. |
| A search engine | Search returns *candidates*; the model decides relevance. There is no relevance ranking. |
| An agent framework | Kedu does not run, orchestrate, or prompt agents. It records sessions and hands off context. |
| Platform memory | Records are local files you own and can read, diff, and redact — not vendor-held memory. |

## Try it from source

> Source-first only. There is no `npm install -g kedu`, `brew install kedu`, or `pip install
> kedu` yet.

```bash
git clone https://github.com/jasonshrepo/kedu.git
cd kedu

# Install the `kedu` shim (to ~/.local/bin) and an engine copy (to ~/.kedu/kedu)
bash install.sh

# Optional: macOS LaunchAgent for scheduled maintenance
bash install.sh --install-launchd
```

Make sure `~/.local/bin` is on your `PATH`, then:

```bash
kedu --help
```

The shared store defaults to `~/.kedu`; override it with `export KEDU_HOME=/path/to/store`.
All agents share one store — agent identity is recorded on each record, not in separate
per-agent stores.

### Developing on Kedu

```bash
uv sync          # install dependencies (Python >=3.11, duckdb)
uv run pytest    # run the test suite
```

## Workflow

These are real commands implemented in this repo.

**Wire a project to an agent** (project-local by default):

```bash
cd /path/to/project
kedu init --host claude        # or codex | cursor | kiro
kedu init --host claude --global   # optional user-level defaults
```

**Capture a record:**

```bash
kedu log --source manual --agent claude --project my-project --body record.json
```

`--body` takes a path to a JSON record; if omitted, `kedu log` reads JSON from stdin. The
body is validated, redacted, then appended to the hot and durable tiers, and `STATE.md` is
rebuilt.

**Retrieve records** (candidate identification, not ranking):

```bash
kedu search --scope current_project --query "auth cookie"
kedu search --scope all --tags security --since 2026-01-01
kedu search --scope current_project --agent codex --query "deploy" --ids-only
kedu show '<session-id>:1'
```

**Read the derived boot view:**

```bash
kedu state --project my-project          # print STATE.md
kedu rebuild-state --project my-project   # regenerate it from all tiers
```

**Maintain and redact:**

```bash
kedu maintain --dry-run        # preview rotation + archival; drop --dry-run to apply
kedu redact --value "secret-value" --reason "leaked in session"
```

**Remove Kedu wiring** (records are never deleted):

```bash
kedu uninstall --dry-run       # preview; drop --dry-run to apply
```

### Where records anchor

`kedu log` resolves the project root by precedence: `KEDU_PROJECT_ROOT` → the nearest
ancestor with a `.kedu/config.json` init marker → the git repository root → the current
directory. The slug is read from the init marker, so records stay anchored to the project
root even when an agent runs `kedu log` from a subdirectory, and the slug is stable across
renames. If none of these identify a root and no `--project` is given, `kedu log` stops
rather than create a stray identity — run `kedu init` first, pass `--project`, or set
`KEDU_PROJECT_ROOT`.

## Record structure

A local init creates a project-local `.kedu/` directory, and the shared store lives under
`~/.kedu` (or `$KEDU_HOME`):

```text
<project>/.kedu/
├── short.jsonl     # hot tier: 7-day rolling window, project-local
├── STATE.md        # derived boot view (open items, decisions, entry index)
└── config.json     # init marker + canonical project slug

~/.kedu/
├── long/<project>.jsonl                                   # durable tier: all records
├── archive/project=<name>/month=<YYYY-MM>/entries.parquet # aged records (DuckDB Parquet)
├── query_log.jsonl
└── redaction_log.jsonl
```

Each record is a JSON object (schema version 2) with these fields:

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

Records are written to the hot and durable tiers on every `log`, deduplicated by `id`, and
aged into Parquet by `kedu maintain`.

## Design principles

- **Local-first by default** — records live in your repo and `~/.kedu`, not a vendor service.
- **Lossless before clever** — store the full record, not a lossy summary.
- **Verified records over synthetic memory** — captured handoffs, not model-invented recall.
- **Deterministic retrieval before model reasoning** — exact filters and scans find
  candidates; the model judges relevance.
- **Inspectable files over black-box recall** — plain JSONL and Markdown you can read,
  diff, and redact.
- **Developer-owned history over platform-owned memory** — your files, your store, your
  control.

## Roadmap

Implemented:

- [x] Stable local record format (JSONL hot/durable + Parquet archive, schema v2)
- [x] Session capture workflow (`kedu log`)
- [x] Deterministic retrieval (`kedu search` / `kedu show`)
- [x] Derived project state (`kedu state` / `STATE.md`)
- [x] Write-time and retroactive redaction (`kedu redact`)
- [x] Archival tiering to Parquet (`kedu maintain`)
- [x] Multi-host wiring (Claude, Codex, Cursor, Kiro) and clean uninstall
- [x] Stable project-root resolution via init marker

Planned / not yet implemented:

- [ ] Git-aware file-change context captured into records
- [ ] Packaged install (PyPI / Homebrew) and versioned releases
- [ ] MCP server interface for agents
- [ ] Agent-specific handoff templates beyond host wiring
- [ ] Documentation site

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Jason Shen.
