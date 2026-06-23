# Redaction and Privacy

Qiju is local-first, but local-first does not mean secret-safe. The best policy is
to avoid recording credentials, secrets, PII, customer data, or other sensitive
values in the first place.

## What Qiju does

At write time, Qiju applies:

- regex rules for common credential and PII-like patterns;
- high-entropy token detection;
- an allowlist for known-safe values such as commit hashes.

When a known value has already been stored, `qiju redact` can retroactively replace
that literal value across:

- project hot JSONL;
- durable user-level JSONL;
- archive Parquet files.

Each retroactive redaction appends an audit event to
`~/.qiju/redaction_log.jsonl`.

## What Qiju does not promise

Redaction is best-effort. Regex rules and entropy checks cannot detect all
sensitive information, especially:

- names;
- physical addresses;
- customer-specific identifiers;
- context-dependent secrets;
- free-form sensitive narratives.

Qiju is not a DLP product and should not be marketed as one.

## Privacy boundaries

Qiju records are local by default and Qiju does not require a hosted Qiju service.
It does not send records to an embedding API and does not require a vector
database.

However, the AI agent you use with Qiju may send prompts, file content, and record
content to that agent provider according to its own policies and configuration.
Qiju does not alter the privacy model of Claude Code, Codex, Kiro, Cursor, or any
future host.

## Retroactive redaction

```bash
qiju redact --value "secret-value" --reason "leaked in session"
```

Blank redaction values are rejected because replacing an empty string would corrupt
every record.

Use precise literal values. If a secret appears in multiple transformed forms,
redact each known form.

