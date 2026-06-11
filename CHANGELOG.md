# Changelog

All notable changes to Kedu are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and Kedu aims to follow
[Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-06-11

Project names are now case-insensitive: every project name is normalized to one canonical
lowercase slug at log time and search time. This closes a bug where a casing slip (e.g.
`MyProject` vs `myproject`) silently forked a project's history into an
unretrievable shadow set — the log succeeded, but `kedu show` / `kedu search` resolved the
other identity. A one-time `kedu migrate` normalizes existing stores.

### Added
- **`kedu projects`** — new subcommand that prints canonical project slugs (one per line),
  sourced from `storage.all_projects()`. Would have surfaced a duplicate project identity
  instantly.
- **`kedu migrate`** — new subcommand (with `--project` and `--dry-run`) that normalizes all
  project names to lowercase slugs across the long JSONL tier, archive Parquet tier, the
  current project's short tier, and its `.kedu/config.json` init marker. Idempotent:
  a second run on an already-normalized store reports no changes.
- **`scripts/migrate.py`** — backing module for `kedu migrate`; handles the case-insensitive
  APFS filesystem correctly (detects same-physical-file via `os.path.samefile` and renames
  in-place rather than writing and unlinking).

### Changed
- **`slugify_project()` now lowercases the slug.** Mixed-case project names like
  `MyProject` and `myproject` previously forked into two silent project
  identities; they now share one canonical lowercase slug (`myproject`). The change
  applies at log time (via `resolve_paths`) and at search time (via `project_slug` /
  `_resolve_scope`).
- **`search_entries` project filter is now case-insensitive.** Legacy un-migrated entries
  whose `project` field is mixed-case still match a lowercase slug query
  (`entry["project"].lower() not in projects`), so records are retrievable before and after
  running `kedu migrate`.
- **`all_projects()` returns lowercase slugs only.** Long-file stems and archive dir names
  are lowercased before being added to the result set, so the project listing is canonical
  and deduplicated even before migration.

### Fixed
- **Project identity forking on case-insensitive filesystems (macOS APFS).** Records logged
  with `--project myproject` vs `MyProject` used to fork into two identities;
  `kedu show` / `kedu search` would resolve one slug while data sat under the other, making
  records silently unretrievable. Lowercase normalization at all entry points closes the bug.

### Notes on upgrading
- Run `kedu migrate --dry-run` to preview, then `kedu migrate` once to normalize an existing
  store: long files and archive partitions are renamed to their lowercase slug and each
  record's `project` field is rewritten. No records are deleted (entries merge and dedupe by
  `id` only), and the command is idempotent.
- Even before migrating, mixed-case records stay retrievable: the search filter matches the
  stored `project` field case-insensitively.

## [0.2.0] - 2026-06-09

A large consolidation release: Kedu is reframed as a local-first **record layer** (not
"memory"), the agent integration is simplified to two single-sourced skills, and several
correctness, safety, and security issues were fixed — including a critical data-loss bug in
`uninstall`.

### Added
- **Two explicit agent skills, `kedu-log` and `kedu-search`**, generated from a single shared
  template per host (Claude / Codex / Kiro as `SKILL.md`; Cursor as one
  `.cursor/rules/kedu.mdc`). Replaces the prior unified `/kedu` skill. One source of truth, so
  the four host copies can no longer drift apart.
- **`kedu search --format actions`** — rolls up open `next_steps` across the matching records
  into a single deduplicated checklist, so "what's still pending?" needs no external scripting.
- **More write-time redaction patterns** — GitHub tokens & fine-grained PATs, Slack tokens,
  Google API keys, Stripe keys, OpenAI/Anthropic keys, JWTs, US phone numbers, US SSNs,
  credit-card numbers, and IPv4 addresses.
- **Redaction ruleset validation** — malformed JSON or an uncompilable regex in the rules is
  caught by tests before it can break logging at runtime.
- **Timestamp validation** — `kedu log` coerces a missing or unparseable `ts` to now (lossless,
  never drops a record); `schema.validate` rejects non-ISO timestamps from non-capture writers.
- **`kedu uninstall` cleans every Kedu-enabled project by default** (`--no-scan-projects` to
  limit to the current project) and removes the runtime lock file `~/.kedu/.kedu.lock`.
- **Chinese README** (`README.zh.md`) with an English / 中文 language switcher in both versions.
- **Config shipped as package data** (`scripts/config/`) so future wheel/sdist builds include
  `redaction_rules.json` and `allowlist.json`.

### Changed
- **Positioning** — Kedu is described as a local-first *record layer*: it records what
  happened, who did it, where the evidence is, and what should happen next. README, package
  description, and skill guidance updated accordingly.
- **Short (hot) memory window widened from 7 to 14 days.**
- **Uniform redaction token** — every redacted match (regex rules + high-entropy detection) is
  replaced by a salted SHA-256 token `[REDACTED:pii:<digest>]` (random per-process salt, never
  written to disk), instead of per-rule placeholders.
- **Claude integration is fully skill-first** — `kedu init` no longer appends an always-on
  block to `CLAUDE.md`; the two skills are the entire integration.
- **Redaction config relocated** from a top-level `config/` directory into the `scripts/config/`
  package.
- **Reinstall prunes stale engine files** before extracting (keeps the `.venv`, never touches
  records), so files removed in a newer version no longer linger in `~/.kedu/kedu`.
- **Installer** rejects a missing option value (e.g. `--prefix` with no argument) with a clear
  error instead of a raw shell `unbound variable` crash.

### Removed
- **`STATE.md`** — the generated boot/index file is gone end to end (the module, the
  rebuild-after-every-log step, and the `kedu state` / `kedu rebuild-state` commands).
  Orientation and recall are user-driven via `kedu search`.
- **`query_log.jsonl`** feature — searches are no longer logged; any pre-existing
  `query_log.jsonl` is removed on uninstall. (The `redaction_log.jsonl` audit trail is kept.)
- **Kiro steering** — Kiro is now skill-first (the `/kedu-*` skills plus a CLI agent config);
  legacy steering/prompt artifacts are still purged on uninstall for older installs.
- The retired `clean_exit` source value from adapter usage and active design docs.
- Deprecated/stale release artifacts and stray empty directories.

### Fixed
- **CRITICAL (data loss): `kedu uninstall` could delete the entire global store.** When run
  from a directory whose `.kedu` resolves to `KEDU_HOME` (for example from `$HOME`), the
  project-cleanup path treated `~/.kedu` as a project directory and removed it — wiping
  `long/` and `archive/` (all records). A guard now refuses to prune any project `.kedu` that
  is, or contains, the global store. **Uninstall never deletes memory, from anywhere.**
- `kedu maintain`, time-filtered `kedu search`, and state rebuild no longer crash on a
  pre-existing record with a malformed `ts`.
- Reinstalling no longer leaves stale scripts/templates/tests behind in the installed engine.

### Security
- **Retroactive redaction rejects an empty / whitespace `--value`.** Previously a blank value
  inserted the placeholder between every character of every field, corrupting all tiers.
- **The retroactive-redaction audit `reason` is redacted before it is written**, so a secret
  accidentally included in `--reason` no longer leaks into `redaction_log.jsonl`.
- Agent skills instruct agents to keep PII, credentials, and secrets out of records, with
  explicit definitions of each.

### Notes on upgrading
- Records are fully backward compatible; nothing is rewritten. Your `~/.kedu` store and each
  project's `.kedu/short.jsonl` carry over untouched.
- Re-run `kedu init --host <host>` in each project to pick up the new `kedu-log` / `kedu-search`
  skills (the old unified `/kedu` skill is replaced).

## [0.1.0] - 2026-06-03

- Initial public developer-preview release: intentional session-record capture (`kedu log`),
  deterministic retrieval (`kedu search` / `kedu show`), maintenance and archiving
  (`kedu maintain`), write-time and retroactive redaction (`kedu redact`), and per-host wiring
  (`kedu init` / `kedu uninstall`) across Claude, Codex, Kiro, and Cursor. Local-first JSONL +
  DuckDB Parquet storage tiers.
