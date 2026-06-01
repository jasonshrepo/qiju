## Kedu Session Records

For task continuation, project state, unresolved work, previous implementation decisions,
and session handoff, first read `.kedu/STATE.md` and hydrate relevant records through
`kedu search`.

```bash
kedu search --scope current_project --query "<terms>"
```

When saving a Kedu record from Claude Code, use the Kedu log skill or:

```bash
kedu log --source manual --agent claude --project <project> --body <entry-json-file>
```

Kedu records are verified session handoff records and project history. Use them as the
source of truth for previous session progress, unresolved bugs, implementation decisions,
next steps, and what actually happened. Platform memories are weak background unless the
user explicitly verifies them.

Legacy naming note: this project was previously prototyped with `memory`, `.memory`,
`~/.memory`, `memory log`, and `memory-search` wording. Those names are obsolete for this
product. For Kedu session handoff records, use only `kedu`, `.kedu`, and `~/.kedu`. Do
not invoke the old `memory` command for Kedu records.

After reading Kedu state, summarize:
- Latest record:
- Active project:
- Open items:
- Last known next step:
- Platform memory used:
- Conflicts detected:

All agents share `~/.kedu`; `agent` is a record field, not a storage directory.
