---
name: kedu-search
description: Use when the user asks about previous sessions, past decisions, unresolved bugs, what was already done, what's still pending, or invokes `/kedu-search`; retrieves Kedu records.
---

# Search Kedu Session Records

Use this skill to retrieve project history through the `kedu` CLI. Trigger it when the
user asks about previous sessions, past decisions, unresolved bugs, what was already done,
what's still pending, or invokes `/kedu-search`.

## Shape output with kedu's own flags

NEVER pipe `kedu` output through `python`, `jq`, `awk`, or `sed`. `kedu search` already
emits exactly the shape you need — ask it for that shape:

- `--fields a,b,c` — keep only these fields, e.g. `--fields title,ts,next_steps`.
- `--format json|jsonl|summary|table|actions` — pick the rendering. `summary` is one line
  per record; `table` is columnar; `actions` rolls up open next steps as a checklist.
- `--ids-only` — return just ids (plus project/title) for a follow-up `kedu show <id>`.
- `--limit N` — cap the number of results.

Examples:

```bash
kedu search --scope current_project --query "auth cookie" --format summary
kedu search --scope current_project --fields title,ts --limit 5
kedu search --scope current_project --ids-only --query "deploy"
```

## Confirm the time range before a wide search

Infer the query's time span and act accordingly:

- Clearly recent ("yesterday", "this week"): just search.
- Open-ended ("everything I've worked on") or clearly older than ~14 days (reaching into
  the long/archive tiers): CONFIRM the intended range with the user before running the
  wide search, so you don't dump the entire history unasked.

Translate plain time phrases into bounds: "since Monday" → `--since`, "before March" →
`--until`. Pass ISO dates, e.g. `--since 2026-06-01 --until 2026-06-08`.

## Pending / open action items

When the user asks "what's pending?" or "what are the open action items?", roll up the
outstanding next steps:

```bash
kedu search --scope current_project --format actions
```

## Scope

Default to `--scope current_project`. Widen to `--scope all` only for cross-project
questions.

```bash
kedu search --scope current_project --query "<terms>"
```

## Two-phase retrieval

`kedu search` = **Phase 1: candidate identification.** Finds records and prints ids in
`<uuid>:N` form. Use `--ids-only` or `--format summary` for a cheap candidate manifest:

```bash
kedu search --scope current_project --query "deploy" --ids-only   # Phase 1: candidate ids
```

`kedu show <uuid>:N` = **Phase 2: hydrate.** Fetches the full body of the chosen record:

```bash
kedu show "<uuid>:N"   # Phase 2: hydrate one record
```

**id-format rule:** ids are always `<uuid>:N`. Pass the id to `kedu show` EXACTLY as
`kedu search` prints it, INCLUDING the `:N` suffix. A bare UUID (no `:N`) returns
'record not found'.

**bare-UUID routing:** if you only hold a bare UUID (e.g. copied from a record-body
cross-reference), do NOT call `kedu show` with it — run `kedu search` first to recover
the full `<uuid>:N` id. Never strip or guess `:N`.

Kedu records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them.

Legacy naming note: this project was previously prototyped with
`memory`, `.memory`, `~/.memory`, `memory log`, and `memory-search` wording. Those names
are obsolete for this product. For Kedu session handoff records, use only `kedu`,
`.kedu`, and `~/.kedu`. Do not invoke the old `memory` command for Kedu records.
