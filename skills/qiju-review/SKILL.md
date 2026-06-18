---
name: qiju-review
description: Manually invoked retrospective for Qiju records. Use when the user explicitly asks to review recent Qiju project and global records, extract mistakes and lessons learned from the last 7 days, and recommend improvements to work-related skills, prompts, guardrails, or verification habits.
---

# Qiju Review

## Overview

Use this skill to turn recent Qiju session records into practical skill and prompt improvements. Focus on mistakes, missed guardrails, unclear instructions, repeated friction, and lessons that should change how future work is guided.

Do not edit any skill files unless the user explicitly asks. Produce recommendations and proposed wording only.

## Collect Records

Use Qiju records as the evidence source. Platform memory is background only unless the user explicitly verifies it.

1. Compute the 7-day window from the current date and timezone. State the exact `--since` and `--until` dates used.
2. Read both project and global records:
   - Project records: `qiju search --scope current_project --since <date> --until <date> --format summary --limit <N>`
   - Global/cross-project records: `qiju search --scope all --since <date> --until <date> --format summary --limit <N>`
3. Hydrate relevant records with `qiju show <id>` when the summary suggests a mistake, unresolved issue, repeated fix cycle, prompt confusion, verification failure, or skill-related lesson.
4. Prefer Qiju's own flags such as `--fields`, `--format`, `--ids-only`, `--since`, `--until`, and `--limit`. Do not pipe Qiju output through ad hoc text-processing commands when Qiju can shape the output directly.
5. If the Qiju CLI shape is unclear, inspect `qiju search --help` or use the local `qiju-search` skill if available.

## Extract Lessons

Look for evidence-backed patterns, not isolated annoyances. Treat something as skill-worthy when it is recurring, high-impact, easy to prevent with guidance, or caused by unclear existing instructions.

Extract:

- Mistakes: wrong assumptions, broken commands, missed permissions, destructive-risk moments, skipped verification, wrong source of truth, poor handoff quality.
- Lessons learned: what future Codex should do differently in similar work.
- Skill or prompt causes: instructions that were ambiguous, missing, too broad, too narrow, stale, unused, or counterproductive.
- Positive guardrails: existing prompts or skills that prevented mistakes and should be kept.

Avoid overfitting:

- Do not recommend changing a skill from one weak signal unless the impact was severe.
- Do not blame a skill when the record points to missing project context, user preference, external failure, or one-off environment trouble.
- Do not invent missing record details. Mark gaps as "unknown from records."

## Recommendation Types

For each candidate improvement, choose one:

- `add`: Add a guardrail, verification step, source-of-truth reminder, or output format requirement.
- `rewrite`: Make an unclear prompt more specific, shorter, or easier to follow.
- `remove`: Delete guidance that caused wasted work, conflict, or repeated confusion.
- `split`: Move bulky or conditional guidance into a separate reference or narrower skill.
- `keep`: Preserve useful guidance and explain why no change is needed.
- `monitor`: Watch for another week before changing anything.

When recommending new or rewritten prompt text, make it copy-ready and scoped. Prefer imperative instructions over explanations.

## Output Format

Produce a concise report:

```markdown
# 7-Day Qiju Review

Window: <start date> to <end date>
Sources: <project/current_project count>, <global/all count>, <hydrated record ids>

## Recurring Mistakes and Lessons
- Pattern:
  Evidence:
  Lesson:
  Skill relevance:

## Skill and Prompt Recommendations
- Target:
  Type: add | rewrite | remove | split | keep | monitor
  Why:
  Suggested wording:
  Confidence: high | medium | low

## Do Not Change
- Target:
  Reason:

## Highest-Leverage Next Edits
1. ...
2. ...
3. ...
```

Keep the report evidence-first. Mention record ids or titles where useful, but avoid copying secrets, credentials, PII, or sensitive operational details from records.

## Optional Follow-Up

If the user asks to apply recommendations, edit only the targeted skill files, validate any changed skills, and record the change with Qiju when appropriate.
