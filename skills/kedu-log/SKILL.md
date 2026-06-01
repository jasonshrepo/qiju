# kedu-log — Capture Session To Kedu

Use this skill when the user invokes `/log`, asks to save/checkpoint the current work, or asks to create a durable Kedu record.

1. Summarize the current session into a structured JSON object with:
   - `title`: one-line summary
   - `agent`: the current host/agent identity, such as `claude`, `codex`, or `kiro`
   - `tags`: 3-5 categories
   - `search_terms`: aliases, service names, error codes, symbols, and useful variants
   - `next_steps`: actionable remaining items
   - `body_md`: full human-readable markdown narrative
2. Write that JSON object to a temp file.
3. Run `kedu log --source manual --agent <agent> --project <project> --body <temp-file>`.
4. Report the returned record id.

Do not include secrets. The CLI runs write-time redaction before persistence.
