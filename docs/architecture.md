# Qiju Architecture

Qiju is a local-first record and handoff layer for AI coding sessions. It stores
intentional, structured records in local files and retrieves them with explicit
filters before an agent reasons over the selected records. "Lossless" means the
record is preserved after capture; Qiju does not preserve a raw transcript unless
the user deliberately writes one into a record.

## Storage and retention

Every logged record is written to both the project hot tier and the durable
user-level tier. Maintenance can later archive older durable records into
partitioned Parquet files.

| Tier | Location | Purpose |
| --- | --- | --- |
| Hot | `<project>/.qiju/short.jsonl` | Recent project context |
| Durable | `~/.qiju/long/<project>.jsonl` | Complete retained project record |
| Archive | `~/.qiju/archive/project=<name>/month=<YYYY-MM>/entries.parquet` | Long-term local archive |

`qiju maintain` currently uses these thresholds:

- hot tier rotation: entries older than 14 days are removed from
  `<project>/.qiju/short.jsonl`;
- stale staging sweep: managed staging files older than 24 hours are removed;
- durable archive eligibility: month partitions older than 92 days are archived
  when they exceed 2 MiB;
- small old partitions are archived once all entries are older than 366 days;
- if a durable JSONL file exceeds 50 MiB, entries older than 31 days are
  force-eligible for archival.

Reads merge all three tiers and deduplicate records by `id`.

## Record schema

Records use schema version 2. Required fields:

```json
{
  "schema_version": 2,
  "id": "<session-uuid>:<sequence>",
  "ts": "2026-06-23T10:00:00+10:00",
  "project": "my-project",
  "agent": "codex",
  "source": "manual",
  "title": "One-line summary",
  "tags": ["architecture", "handoff"],
  "search_terms": ["aliases", "error-codes", "symbols"],
  "next_steps": ["actionable item"],
  "redactions": [],
  "body_md": "Full human-readable Markdown narrative"
}
```

Valid `source` values are `manual` and `agent`. Qiju validates record shape before
write and redacts configured sensitive patterns before persistence.

## Capture lifecycle

1. `qiju temp-entry --agent <host>` allocates an empty, unique staging file under
   `.qiju/tmp/`.
2. The agent writes a JSON record to that file.
3. `qiju log --source manual --agent <host> --body <path> --cleanup` validates,
   redacts, and ingests the record.
4. The record is appended to the hot and durable tiers.
5. `--cleanup` deletes only Qiju-managed staging files after successful ingestion.

Qiju does not capture sessions silently and does not ingest raw transcripts.

## Retrieval

`qiju search` identifies candidate records. It can filter by:

- scope: current project, all projects, or named project list;
- project;
- source;
- agent;
- session UUID prefix;
- tags;
- `--since` and `--until` time bounds;
- keyword query;
- regex query;
- result format and selected fields.

Search scans `agent`, `title`, `body_md`, `tags`, `search_terms`, and
`next_steps`. Plain keyword matching is case-insensitive and OR-based across
terms. Regex search uses Python regular expressions with case-insensitive,
multiline matching.

`qiju show '<uuid>:N'` hydrates one full record by exact ID. The `:N` suffix is
part of the record ID and must be preserved.

There are no embeddings, vector indexes, relevance scores, or external search
services in the current implementation.

## Project identity

Qiju resolves the project root in this order:

1. `QIJU_PROJECT_ROOT`
2. nearest ancestor containing `.qiju/config.json`
3. Git top-level directory
4. current working directory fallback

`qiju init` writes `.qiju/config.json`, including the canonical project slug.
That marker keeps records anchored to the initialized root even when an agent
runs commands from a subdirectory.

Project names are slug-normalized to lowercase. This prevents `MyProject` and
`myproject` from splitting a project's history.

When `qiju log` would otherwise mint a new identity from a bare current working
directory, it refuses the write and asks the caller to run `qiju init`, pass
`--project`, or set `QIJU_PROJECT_ROOT`.

## Lifecycle operations

- `qiju maintain` rotates the hot tier, sweeps old staging files, and archives
  durable records into Parquet.
- `qiju migrate` normalizes project names across JSONL, Parquet, short-tier, and
  marker files.
- `qiju migrate --from-kedu` copies a legacy `~/.kedu` store into `~/.qiju`,
  rebranding record content and preserving the old store as a backup.
- `qiju update` refreshes installed skill files across registered projects and
  can scan project roots to backfill `~/.qiju/registry.d/`.
- `qiju uninstall` removes host integration files and runtime installation state
  while preserving records by default.
