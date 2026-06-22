---
name: qiju-log
description: Use when the user asks to save, checkpoint, or hand off durable project context, record what was done or decided, or invokes `/qiju-log`; writes a verified Qiju session handoff record.
---

# Save a Qiju Session Record

Use this skill to capture a durable, verified session handoff record through the `qiju`
CLI. Trigger it when the user asks to save, checkpoint, remember, or hand off project
context, or invokes `/qiju-log`.

## Steps

1. Summarize the current session, decision, or requested fact into a single JSON object:
   - `title`: one-line summary.
   - `tags`: 3-5 categories.
   - `search_terms`: aliases, service names, error codes, symbols, and useful variants.
   - `next_steps`: actionable remaining items.
   - `body_md`: full human-readable markdown narrative. Do not shorten it to save space —
     the body is the handoff; storage is negligible.
2. Allocate a unique workspace-local staging file (Qiju owns the name):

   ```bash
   path="$(qiju temp-entry --agent claude)"
   ```

   This returns a path under `.qiju/tmp/` (inside the workspace — never `/tmp`; some hosts
   reject writes outside the workspace).
3. Write the JSON object to exactly that `$path`. Then ingest and let Qiju delete it:

   ```bash
   qiju log --source manual --agent claude --project <project> --body "$path" --cleanup
   ```
4. Qiju removes the staging file on success — do not delete it yourself.
5. Report the returned record id.

Do NOT include PII, credentials, secrets, or other sensitive
information in Qiju summaries or records. Keep following the Qiju principles for useful
session handoff records, but exclude or summarize around sensitive values.
- Credentials/secrets: passwords, API keys, access/refresh tokens, session cookies,
  private or SSH keys, signing/encryption keys, database URLs with embedded credentials,
  cloud credentials, and any value that grants access.
- PII: email addresses, phone numbers, physical addresses, government IDs, dates of birth,
  payment/bank data, precise personal location, health or financial data, and
  customer/user data tied to a person.
Write-time redaction is a best-effort backstop, not a license to paste secrets.

Qiju records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them.

Legacy naming note: this project was previously prototyped with
`memory`, `.memory`, `~/.memory`, `memory log`, and `memory-search` wording. Those names
are obsolete for this product. For Qiju session handoff records, use only `qiju`,
`.qiju`, and `~/.qiju`. Do not invoke the old `memory` command for Qiju records.
