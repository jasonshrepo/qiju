---
name: kedu-log
description: Use when the user asks to save, checkpoint, or hand off durable project context, record what was done or decided, or invokes `/kedu-log`; writes a verified Kedu session handoff record.
---

# Save a Kedu Session Record

Use this skill to capture a durable, verified session handoff record through the `kedu`
CLI. Trigger it when the user asks to save, checkpoint, remember, or hand off project
context, or invokes `/kedu-log`.

## Steps

1. Summarize the current session, decision, or requested fact into a single JSON object:
   - `title`: one-line summary.
   - `tags`: 3-5 categories.
   - `search_terms`: aliases, service names, error codes, symbols, and useful variants.
   - `next_steps`: actionable remaining items.
   - `body_md`: full human-readable markdown narrative. Do not shorten it to save space —
     the body is the handoff; storage is negligible.
2. Write that JSON object to `.kedu/kedu-entry.json` INSIDE the workspace. Never write it
   to `/tmp` (some hosts reject writes outside the workspace).
3. Run:

   ```bash
   kedu log --source manual --agent claude --project <project> --body .kedu/kedu-entry.json
   ```
4. Remove `.kedu/kedu-entry.json` after a successful log.
5. Report the returned record id.

Do NOT include PII, credentials, secrets, or other sensitive
information in Kedu summaries or records. Keep following the Kedu principles for useful
session handoff records, but exclude or summarize around sensitive values.
- Credentials/secrets: passwords, API keys, access/refresh tokens, session cookies,
  private or SSH keys, signing/encryption keys, database URLs with embedded credentials,
  cloud credentials, and any value that grants access.
- PII: email addresses, phone numbers, physical addresses, government IDs, dates of birth,
  payment/bank data, precise personal location, health or financial data, and
  customer/user data tied to a person.
Write-time redaction is a best-effort backstop, not a license to paste secrets.

Kedu records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them.

Legacy naming note: this project was previously prototyped with
`memory`, `.memory`, `~/.memory`, `memory log`, and `memory-search` wording. Those names
are obsolete for this product. For Kedu session handoff records, use only `kedu`,
`.kedu`, and `~/.kedu`. Do not invoke the old `memory` command for Kedu records.
