# Changelog

All notable changes to QiJu are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and QiJu aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.2] - 2026-06-22

### Changed
- **README and PyPI metadata updated for public release** — `uv tool install qiju` is now
  the primary installation path, with `pipx install qiju`, `pip install qiju`, and
  `uvx qiju --help` documented as alternatives. The `git clone` + `bash install.sh` path
  is moved to a clearly labeled "Source install" subsection (still needed for macOS
  launchd or contributing). All claims of source-only or no package-manager release
  removed. No code or behavior changes.
- **Deterministic builds** — `build.sh` now sets `SOURCE_DATE_EPOCH` to the last
  `release/` git commit timestamp before invoking `uv build`, so successive builds from
  the same source produce identical byte-for-byte artifacts.

## [0.5.1] - 2026-06-22

### Changed
- **Source layout restructured to `src/qiju/`** — canonical package is now `qiju` (was
  `scripts`); entry point changed to `qiju.cli:main`. Tests import from `qiju` directly.
  No user-facing behavior changes.
- **Single version source** — version is now defined only in `pyproject.toml` and read at
  runtime via `importlib.metadata`; `QIJU_VERSION` constant removed from source.
- **Resource loading via `importlib.resources`** — `allowlist.py` and `redact.py` now load
  config files through `importlib.resources.files("qiju")` instead of `Path(__file__)`,
  enabling correct loading from a wheel's site-packages.
- **`install.sh` version derived from `pyproject.toml`** — no more hardcoded `VERSION=`;
  launchd `ProgramArguments` now invokes the console-script entry point instead of the
  source `scripts/qiju.py` path.
- **Data-purge separation** — `qiju uninstall` never deletes records by default; explicit
  `qiju uninstall --purge-data [--yes]` is the only path to remove `~/.qiju/long|archive`.

## [0.5.0] - 2026-06-22

### Added
- **Concurrency-safe staging files** — new `qiju temp-entry` command allocates a unique,
  workspace-local staging file (`.qiju/tmp/qiju-entry.<agent>.<uuid>.json`) via atomic
  exclusive create. This removes the race where two agents logging at the same time in the
  same project could overwrite, delete, or read a torn copy of the previously shared
  `.qiju/qiju-entry.json`.
- **Guarded `qiju log --cleanup`** — after a successful durable write, `qiju log` deletes
  the `--body` file only when it is a Qiju-managed staging file. The guard rejects symlinks,
  `../` traversal, and paths outside `.qiju/tmp/`, so it never deletes an arbitrary
  user-provided file; a refused cleanup warns but does not fail the log.
- **Stale staging-file sweep** — `qiju maintain` now removes abandoned
  `.qiju/tmp/qiju-entry.*.json` files older than 24h (left behind by crashed agents),
  applying the same symlink/containment safety checks.
- **`qiju-review` skill** — a project-owned retrospective skill for reviewing recent QiJu
  records, extracting lessons, and recommending prompt/skill improvements.
- **Provider-neutral skill layout** — QiJu now ships only portable
  `skills/<skill-name>/SKILL.md` packages and no provider-specific metadata files such as
  `agents/openai.yaml`. Cursor now uses `.cursor/skills/<skill-name>/SKILL.md` instead of a
  `.cursor/rules/qiju.mdc` rule, and Kiro no longer generates `.kiro/agents/qiju.json`;
  cleanup still removes those legacy files if present.

### Changed
- **`qiju-log` skill workflow** — the generated and shipped `qiju-log` instructions now
  allocate a staging file with `qiju temp-entry`, write the record to it, and ingest with
  `qiju log --body "$path" --cleanup` (Qiju removes the file on success) instead of writing
  to the fixed `.qiju/qiju-entry.json` and deleting it by hand.

### Fixed
- **Legacy Codex skill cleanup** — `qiju uninstall --hosts codex` now removes stale
  `CODEX_HOME/skills/qiju-log`, `qiju-search`, and `qiju-review` directories left by older
  installs, preventing duplicate personal/project QiJu skills in Codex.

## [0.4.0] - 2026-06-16

The project was renamed **Kedu (刻牍) → QiJu (起居)** (pronounced "CHEE-joo", after the
court diarists of imperial China). The CLI, environment variables, directories, and skills
all move from `kedu`/`KEDU`/`.kedu` to `qiju`/`QIJU`/`.qiju`. Existing records are migrated
losslessly — nothing is moved or deleted.

### Changed
- **Renamed everywhere:** command `kedu` → `qiju`; env `KEDU_*` → `QIJU_*`; directories
  `.kedu/` → `.qiju/` and `~/.kedu` → `~/.qiju`; skills `kedu-log`/`kedu-search`/`kedu-lessons-review`
  → `qiju-log`/`qiju-search`/`qiju-review`. Legacy Kedu (刻牍) installs are supported through
  the migration path.

### Added
- **`qiju migrate --from-kedu`** — lossless migration that **copies** `~/.kedu` → `~/.qiju`
  (never moves), deep-rewriting every casing of `kedu` → `qiju` in record bodies and keys,
  and renaming long/archive files. Auto-invoked by `install.sh`; idempotent via a
  `~/.qiju/migrated_from_kedu.json` sentinel. The legacy `~/.kedu` store is left intact as a
  backup.

## [0.3.1] - 2026-06-14

Retrieval is now explicitly two-phase, and `qiju show` guides you back on track when handed
a malformed id. `qiju search` identifies candidate records and prints `{session-uuid}:{seq}`
ids; `qiju show` hydrates one record by that exact id. A bare UUID (the `:N` suffix stripped)
denotes a whole session, not a single record, so it can't hydrate — previously this returned
a bare `record not found`.

### Changed
- **`qiju show` fails helpfully on a malformed id.** A bare UUID (no `:N`) now returns
  `record not found` with a hint to add the `:N` suffix (e.g. `<uuid>:1`); a well-formed but
  missing `<uuid>:N` returns the generic "run `qiju search`" hint. Exit code is unchanged
  (1). The success path is unchanged.
- **Documented the two-phase retrieval model** (search = candidate identification, show =
  hydrate by exact `<uuid>:N`) across both READMEs, the `qiju-search` skill, and the embedded
  agent-init copies, so installed hosts carry the guidance.

### Added
- Test coverage for the bare-UUID `show` error message.

## [0.3.0] - 2026-06-11

Project names are now case-insensitive: every project name is normalized to one canonical
lowercase slug at log time and search time. This closes a bug where a casing slip (e.g.
`MyProject` vs `myproject`) silently forked a project's history into an
unretrievable shadow set — the log succeeded, but `qiju show` / `qiju search` resolved the
other identity. A one-time `qiju migrate` normalizes existing stores.

### Added
- **`qiju projects`** — new subcommand that prints canonical project slugs (one per line),
  sourced from `storage.all_projects()`. Would have surfaced a duplicate project identity
  instantly.
- **`qiju migrate`** — new subcommand (with `--project` and `--dry-run`) that normalizes all
  project names to lowercase slugs across the long JSONL tier, archive Parquet tier, the
  current project's short tier, and its `.qiju/config.json` init marker. Idempotent:
  a second run on an already-normalized store reports no changes.
- **`scripts/migrate.py`** — backing module for `qiju migrate`; handles the case-insensitive
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
  running `qiju migrate`.
- **`all_projects()` returns lowercase slugs only.** Long-file stems and archive dir names
  are lowercased before being added to the result set, so the project listing is canonical
  and deduplicated even before migration.

### Fixed
- **Project identity forking on case-insensitive filesystems (macOS APFS).** Records logged
  with `--project myproject` vs `MyProject` used to fork into two identities;
  `qiju show` / `qiju search` would resolve one slug while data sat under the other, making
  records silently unretrievable. Lowercase normalization at all entry points closes the bug.

### Notes on upgrading
- Run `qiju migrate --dry-run` to preview, then `qiju migrate` once to normalize an existing
  store: long files and archive partitions are renamed to their lowercase slug and each
  record's `project` field is rewritten. No records are deleted (entries merge and dedupe by
  `id` only), and the command is idempotent.
- Even before migrating, mixed-case records stay retrievable: the search filter matches the
  stored `project` field case-insensitively.

## [0.2.0] - 2026-06-09

A large consolidation release: QiJu is reframed as a local-first **record layer** (not
"memory"), the agent integration is simplified to two single-sourced skills, and several
correctness, safety, and security issues were fixed — including a critical data-loss bug in
`uninstall`.

### Added
- **Two explicit agent skills, `qiju-log` and `qiju-search`**, generated from a single shared
  template per host (Claude / Codex / Kiro as `SKILL.md`; Cursor as one
  `.cursor/rules/qiju.mdc`). Replaces the prior unified `/qiju` skill. One source of truth, so
  the four host copies can no longer drift apart.
- **`qiju search --format actions`** — rolls up open `next_steps` across the matching records
  into a single deduplicated checklist, so "what's still pending?" needs no external scripting.
- **More write-time redaction patterns** — GitHub tokens & fine-grained PATs, Slack tokens,
  Google API keys, Stripe keys, OpenAI/Anthropic keys, JWTs, US phone numbers, US SSNs,
  credit-card numbers, and IPv4 addresses.
- **Redaction ruleset validation** — malformed JSON or an uncompilable regex in the rules is
  caught by tests before it can break logging at runtime.
- **Timestamp validation** — `qiju log` coerces a missing or unparseable `ts` to now (lossless,
  never drops a record); `schema.validate` rejects non-ISO timestamps from non-capture writers.
- **`qiju uninstall` cleans every QiJu-enabled project by default** (`--no-scan-projects` to
  limit to the current project) and removes the runtime lock file `~/.qiju/.qiju.lock`.
- **Chinese README** (`README.zh.md`) with an English / 中文 language switcher in both versions.
- **Config shipped as package data** (`scripts/config/`) so future wheel/sdist builds include
  `redaction_rules.json` and `allowlist.json`.

### Changed
- **Positioning** — QiJu is described as a local-first *record layer*: it records what
  happened, who did it, where the evidence is, and what should happen next. README, package
  description, and skill guidance updated accordingly.
- **Short (hot) memory window widened from 7 to 14 days.**
- **Uniform redaction token** — every redacted match (regex rules + high-entropy detection) is
  replaced by a salted SHA-256 token `[REDACTED:pii:<digest>]` (random per-process salt, never
  written to disk), instead of per-rule placeholders.
- **Claude integration is fully skill-first** — `qiju init` no longer appends an always-on
  block to `CLAUDE.md`; the two skills are the entire integration.
- **Redaction config relocated** from a top-level `config/` directory into the `scripts/config/`
  package.
- **Reinstall prunes stale engine files** before extracting (keeps the `.venv`, never touches
  records), so files removed in a newer version no longer linger in `~/.qiju/qiju`.
- **Installer** rejects a missing option value (e.g. `--prefix` with no argument) with a clear
  error instead of a raw shell `unbound variable` crash.

### Removed
- **`STATE.md`** — the generated boot/index file is gone end to end (the module, the
  rebuild-after-every-log step, and the `qiju state` / `qiju rebuild-state` commands).
  Orientation and recall are user-driven via `qiju search`.
- **`query_log.jsonl`** feature — searches are no longer logged; any pre-existing
  `query_log.jsonl` is removed on uninstall. (The `redaction_log.jsonl` audit trail is kept.)
- **Kiro steering** — Kiro is now skill-first (the `/qiju-*` skills plus a CLI agent config);
  legacy steering/prompt artifacts are still purged on uninstall for older installs.
- The retired `clean_exit` source value from adapter usage and active design docs.
- Deprecated/stale release artifacts and stray empty directories.

### Fixed
- **CRITICAL (data loss): `qiju uninstall` could delete the entire global store.** When run
  from a directory whose `.qiju` resolves to `QIJU_HOME` (for example from `$HOME`), the
  project-cleanup path treated `~/.qiju` as a project directory and removed it — wiping
  `long/` and `archive/` (all records). A guard now refuses to prune any project `.qiju` that
  is, or contains, the global store. **Uninstall never deletes memory, from anywhere.**
- `qiju maintain`, time-filtered `qiju search`, and state rebuild no longer crash on a
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
- Records are fully backward compatible; nothing is rewritten. Your `~/.qiju` store and each
  project's `.qiju/short.jsonl` carry over untouched.
- Re-run `qiju init --host <host>` in each project to pick up the new `qiju-log` / `qiju-search`
  skills (the old unified `/qiju` skill is replaced).

## [0.1.0] - 2026-06-03

- Initial public developer-preview release: intentional session-record capture (`qiju log`),
  deterministic retrieval (`qiju search` / `qiju show`), maintenance and archiving
  (`qiju maintain`), write-time and retroactive redaction (`qiju redact`), and per-host wiring
  (`qiju init` / `qiju uninstall`) across Claude, Codex, Kiro, and Cursor. Local-first JSONL +
  DuckDB Parquet storage tiers.
