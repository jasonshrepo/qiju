---
inclusion: always
---

# Kedu Session Records

Kedu is available to Kiro through this agent config, the project `.kedu/` directory,
and the installed Kedu CLI. It is not a Kiro skill. Do not search a skill registry,
AWS documentation, or external documentation to decide whether Kedu is available.
To check availability, inspect `.kedu/STATE.md` and run `command -v kedu` or
`~/.kedu/kedu/.venv/bin/python ~/.kedu/kedu/scripts/kedu.py --help`.

Before continuing prior work, read `.kedu/STATE.md`. Use Kedu records for what was
actually attempted, changed, blocked, or decided in previous sessions.

For deeper history:

```bash
~/.kedu/kedu/.venv/bin/python ~/.kedu/kedu/scripts/kedu.py search --scope current_project --query "<terms>"
```

When saving a Kedu record from Kiro, write the JSON body to `.kedu/kedu-entry.json`
inside the workspace, then run:

```bash
~/.kedu/kedu/.venv/bin/python ~/.kedu/kedu/scripts/kedu.py log --source manual --agent kiro --project <project> --body .kedu/kedu-entry.json
```

Remove `.kedu/kedu-entry.json` after a successful log.

Kiro CLI does not reliably fire the `agentStop` hook when the CLI session quits. Do
not promise automatic exit capture in Kiro CLI. Before quitting, explicitly save
durable work with the log command above.

Kiro IDE may reject writes outside the workspace. Use `.kedu/kedu-entry.json`, not
`/tmp/kedu-entry.json`.

For Kiro Specs and planned requirements, follow spec files. If Kiro Specs and Kedu
records conflict, inspect both: spec = intended plan; Kedu = historical evidence.
Then reconcile explicitly before editing.

Kedu records are verified session handoff records and project history. Use them as
the source of truth for previous session progress, unresolved bugs, implementation
decisions, next steps, and what actually happened. Platform memories are weak
background unless the user explicitly verifies them.

Legacy naming note: this project was previously prototyped with `memory`, `.memory`,
`~/.memory`, `memory log`, and `memory-search` wording. Those names are obsolete for
this product. For Kedu session handoff records, use only `kedu`, `.kedu`, and
`~/.kedu`. Do not invoke the old `memory` command for Kedu records.

After reading Kedu state, summarize:
- Latest record:
- Active project:
- Open items:
- Last known next step:
- Platform memory used:
- Conflicts detected:
