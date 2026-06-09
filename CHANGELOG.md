# Changelog

All notable changes to Kedu are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and Kedu aims to follow
[Semantic Versioning](https://semver.org/).

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
