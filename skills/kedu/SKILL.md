# kedu — Unified Kedu Command

Use this skill when the user invokes `/kedu`, asks to save/checkpoint durable context,
asks to search previous Kedu records, or gives a Kedu-specific instruction such as
`/kedu remember this decision` or `/kedu find the last deployment note`.

Interpret common forms this way:

- `/kedu log`: save a durable session handoff record.
- `/kedu search <query>`: search Kedu records, defaulting to the current project.
- `/kedu <instruction>`: decide whether the instruction is asking to log, search,
  hydrate/show, initialize, or explain Kedu, then perform that action.

## Log

1. Summarize the current session or requested memory into a structured JSON object with:
   - `title`: one-line summary
   - `agent`: the current host/agent identity, such as `claude`, `codex`, or `kiro`
   - `tags`: 3-5 categories
   - `search_terms`: aliases, service names, error codes, symbols, and useful variants
   - `next_steps`: actionable remaining items
   - `body_md`: full human-readable markdown narrative
2. Write that JSON object to a temporary file inside the workspace when possible, such
   as `.kedu/kedu-entry.json`.
3. Run `kedu log --source manual --agent <agent> --project <project> --body <temp-file>`.
4. Remove the temporary file after a successful log.
5. Report the returned record id.

Do not include secrets. The CLI runs write-time redaction before persistence.

## Search

1. Default to `--scope current_project`.
2. Widen to `--scope all` only when the user asks a cross-project question.
3. Convert the question into structured filters plus lexical terms.
4. Add `--agent <agent>` when the user wants records written by a specific agent.
5. Run `kedu search --scope <scope> --query "<terms>"`.
6. If results are incomplete, reformulate with aliases and related terms.
7. Use `kedu show <id>` when you only need to hydrate one candidate.

Kedu search identifies candidates. The model decides relevance for the current turn.

## Initialize

Use `kedu init --host claude` for project-local setup. Use
`kedu init --host claude --global` or `kedu init --host claude --place global` only when
the user wants user-level defaults.
