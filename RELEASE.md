# QiJu Release Process

The process that turns "tests pass" into "it works when a real agent uses it."

Most bugs hit in deployment this project live at the **agent-integration boundary** — the
layer unit tests structurally cannot see (real skill discovery, desktop vs CLI launch
context, the dev→release→install path). This document is the gate that covers that layer.

---

## Two-loop model

Do **not** deploy-test after every feature. Keep a fast inner loop; pass one gate before
release.

```
INNER LOOP — every feature (seconds)
  1. write feature + tests in development/
  2. uv run pytest                       # syntax + unit + contract
  3. for init/install/uninstall changes: # add/update a CONTRACT test that
     assert paths against vendor docs     # asserts the path a REAL agent reads

OUTER LOOP — before release (minutes)
  4. bash sync-release.sh                 # close the dev→release gap
  5. cd release && uv run pytest          # catch sync drift
  6. bash release/install.sh              # install the ACTUAL deployed copy
  7. run the Real-Agent Smoke Matrix      # the integration gate
  8. commit + push release
```

---

## Three test layers

| Layer | Proves | Automatable | Where |
|---|---|---|---|
| **Unit / engine** | storage, search, redaction, maintenance logic | Yes | `tests/` |
| **Contract** | init writes to the paths real agents *actually read*, verified against vendor docs | Yes (fast) | `tests/test_init.py`, `tests/test_install.py` |
| **Real-agent smoke** | skill is discovered + `log`/`search` round-trips in CLI *and* desktop | No — manual checklist | this doc, §Smoke Matrix |

**The bug→test rule:** when you fix a bug, never just patch it — add the test that *would
have caught it*, asserting the correct **external** behavior. A test written to match the
code can only confirm the code. (The Codex skill-path bug passed its test because the test
asserted the buggy path. Contract tests must cite the vendor doc they encode.)

---

## Release Checklist (the outer-loop gate)

Run in order. Do not skip on a "small" change — the small changes are what drift.

### A. Pre-flight (in `development/`)

- [ ] `uv run pytest` — all green.
- [ ] Every init/install/uninstall change has a contract test asserting the real agent
      path, with a comment citing the vendor doc URL.
- [ ] **README.md updated** for any behavior/flag/bug-fix change in this cycle. README is a
      shipped file and must track the code — never let it describe fixed behavior as broken.
- [ ] Internal planning/QA/issue docs live in `development/notes/` (excluded from sync), not
      at the development root; resolved items closed.

### B. Sync to release

- [ ] `bash sync-release.sh`
- [ ] Confirm `release/` contains **no** instance files: no `.qiju/`, `.claude/`,
      `.kiro/`, `.cursor/`, `.agents/`, `CLAUDE.md`, `AGENTS.md`, `*.bak.*`, `notes/`,
      planning docs. (`.gitignore` keeps build artifacts out of commits; sync keeps the
      rest out of the tree.)
- [ ] `cd release && uv run pytest` — all green (catches sync drift / missing files).

### C. Clean install from release

- [ ] `bash release/install.sh`
- [ ] `qiju --help` resolves and runs (confirm `~/.local/bin` is on PATH).
- [ ] Installed code == release code (reinstall is the source of truth; never smoke-test an
      install built from an older sync).

### D. Real-agent smoke (see Smoke Matrix below)

- [ ] Run the matrix for every agent you ship. Each cell must pass or be explicitly marked
      N/A with a reason.

### E. Ship

- [ ] Commit `release/` with a message naming the features/fixes in this cut.
- [ ] Push to the release remote.
- [ ] Tag the version if this is a versioned release.

### F. Post-release sanity

- [ ] `qiju uninstall --dry-run` lists only generated/install files; **never** lists
      `long/`, `archive/`, `redaction_log.jsonl`, or project `.qiju/`
      with records.
- [ ] On a throwaway project: `qiju uninstall` then confirm records above survived.

---

## Real-Agent Smoke Matrix

Open each agent and walk the four checks. "CLI" = launched from a terminal in a project
dir. "Desktop/IDE" = the app, with the project opened as a workspace.

Per-agent checks:

1. **Discover** — agent sees the QiJu skill/instructions (CLI: `$`/`/skills` or equivalent;
   desktop: skill appears or boot instruction fires).
2. **History read** — agent runs `qiju search` to retrieve project history and can summarize it.
3. **Log round-trip** — ask the agent to save a QiJu record; confirm a new `id` is returned
   and the entry lands in `<project>/.qiju/short.jsonl` **and** `~/.qiju/long/<project>.jsonl`.
4. **Search round-trip** — ask the agent to search QiJu; confirm it finds the record just
   logged.

| Agent | Install command | Skill location read | CLI | Desktop/IDE |
|---|---|---|---|---|
| **Claude Code** | `qiju init --host claude` (+ `--global`) | `.claude/skills/qiju-log/SKILL.md` + `.claude/skills/qiju-search/SKILL.md` + `.claude/skills/qiju-review/SKILL.md` (no `CLAUDE.md` block) | ☐ | ☐ |
| **Codex** | `qiju init --host codex` (+ `--global`) | `.agents/skills/qiju-log/` + `.agents/skills/qiju-search/` + `.agents/skills/qiju-review/` (repo) and `~/.agents/skills/...` (user) | ☐ | ☐ |
| **Kiro** | `qiju init --host kiro` | `.kiro/skills/qiju-log/SKILL.md` + `.kiro/skills/qiju-search/SKILL.md` + `.kiro/skills/qiju-review/SKILL.md` (no `.kiro/agents/qiju.json`) | ☐ | ☐ |
| **Cursor** | `qiju init --host cursor` | `.cursor/skills/qiju-log/SKILL.md` + `.cursor/skills/qiju-search/SKILL.md` + `.cursor/skills/qiju-review/SKILL.md` | ☐ | ☐ |

### Known surface notes (must hold each release)

- **Codex desktop** does not inherit a project CWD the way the CLI does. The **global**
  install (`~/.agents/skills/qiju-log/` + `~/.agents/skills/qiju-search/` +
  `~/.agents/skills/qiju-review/`) is what makes the
  skills discoverable in desktop. If a project-only install "works in CLI but not desktop,"
  that is expected — verify the global paths are present.
- **Codex skill path** is `.agents/skills/` (repo) and `~/.agents/skills/` (user), per
  https://developers.openai.com/codex/skills — **not** `~/.codex/skills/`.
- **Kiro** rejects writes to `/tmp`; entry JSON must be written inside the workspace
  (`.qiju/qiju-entry.json`).
- **Records are CLI-written.** A skill/steering/rule file never stores memories — it only
  tells the agent how to call `qiju`. Records always go to `<project>/.qiju/` +
  `~/.qiju/long/`.

---

## Project-root resolution (affects where records land)

`qiju log` resolves the project root by precedence, then anchors the short tier and the
project slug to it:

1. `QIJU_PROJECT_ROOT` env var (host-provided pin, e.g. a SessionEnd hook).
2. Nearest ancestor containing the init marker `.qiju/config.json` (written only by
   `qiju init`, so stray `.qiju/` data dirs in subfolders cannot hijack resolution).
3. `git rev-parse --show-toplevel`.
4. Current working directory — **last resort**.

The slug is read from the marker (`config.json` `project`) when present, so it is stable
across directory renames and identical between `log` and `search --scope current_project`.

Smoke implications:

- **Initialized project (any kind):** records anchor to the `qiju init` root from any
  subdirectory the agent wanders into. Safe.
- **Guard:** if resolution falls through to the cwd fallback *and* there is no marker *and*
  no explicit `--project`, `qiju log` aborts rather than silently minting a new identity.
  When smoke-testing a fresh non-git project, run `qiju init` first (or pass `--project` /
  set `QIJU_PROJECT_ROOT`).

(Resolves Deviation C from the design-alignment notes — the prior cwd-fragmentation bug
where logging from a subfolder created a second project identity.)

---

## When something fails

1. Reproduce with the raw CLI first (`qiju log`, `qiju search`) to isolate engine vs
   integration.
2. If engine: add a failing unit test, fix, confirm green.
3. If integration: add/fix a contract test asserting the correct vendor path, fix init,
   re-run the inner loop, then re-sync and re-smoke.
4. Record the root cause in an `issue-*` file so the next release inherits the lesson.
