from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from . import paths as paths_mod, util
except ImportError:  # pragma: no cover
    import paths as paths_mod  # type: ignore
    import util  # type: ignore


INIT_SCHEMA_VERSION = 1
KNOWN_AGENTS = ("claude", "kiro", "codex", "cursor")

QIJU_PRIORITY = """Qiju records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them."""

SENSITIVE_DATA_WARNING ="""Do NOT include PII, credentials, secrets, or other sensitive
information in Qiju summaries or records. Keep following the Qiju principles for useful
session handoff records, but exclude or summarize around sensitive values.
- Credentials/secrets: passwords, API keys, access/refresh tokens, session cookies,
  private or SSH keys, signing/encryption keys, database URLs with embedded credentials,
  cloud credentials, and any value that grants access.
- PII: email addresses, phone numbers, physical addresses, government IDs, dates of birth,
  payment/bank data, precise personal location, health or financial data, and
  customer/user data tied to a person.
Write-time redaction is a best-effort backstop, not a license to paste secrets."""

LEGACY_MEMORY_OVERRIDE = """Legacy naming note: this project was previously prototyped with
`memory`, `.memory`, `~/.memory`, `memory log`, and `memory-search` wording. Those names
are obsolete for this product. For Qiju session handoff records, use only `qiju`,
`.qiju`, and `~/.qiju`. Do not invoke the old `memory` command for Qiju records."""

QIJU_LOG_SKILL_DESCRIPTION = (
    "Use when the user asks to save, checkpoint, or hand off durable project context, "
    "record what was done or decided, or invokes `/qiju-log`; writes a verified Qiju "
    "session handoff record."
)

QIJU_SEARCH_SKILL_DESCRIPTION = (
    "Use when the user asks about previous sessions, past decisions, unresolved bugs, "
    "what was already done, what's still pending, or invokes `/qiju-search`; retrieves "
    "Qiju records."
)

QIJU_REVIEW_SKILL_DESCRIPTION = (
    "Manually invoked retrospective for Qiju records. Use when the user explicitly asks "
    "to review recent Qiju project and global records, extract mistakes and lessons "
    "learned from the last 7 days, and recommend improvements to work-related skills, "
    "prompts, guardrails, or verification habits."
)

# Shared log skill body. `{agent}` is the host identity (claude, codex, kiro, ...). No
# boot/startup instruction — Qiju logs on request, not on session start.
QIJU_LOG_BODY = f"""# Save a Qiju Session Record

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
   path="$(qiju temp-entry --agent {{agent}})"
   ```

   This returns a path under `.qiju/tmp/` (inside the workspace — never `/tmp`; some hosts
   reject writes outside the workspace).
3. Write the JSON object to exactly that `$path`. Then ingest and let Qiju delete it:

   ```bash
   qiju log --source manual --agent {{agent}} --project <project> --body "$path" --cleanup
   ```
4. Qiju removes the staging file on success — do not delete it yourself.
5. Report the returned record id.

{SENSITIVE_DATA_WARNING}

{QIJU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}
"""

QIJU_REVIEW_BODY = """# Qiju Review

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
"""

# Shared search skill body — host-independent (no `{agent}` token).
QIJU_SEARCH_BODY = f"""# Search Qiju Session Records

Use this skill to retrieve project history through the `qiju` CLI. Trigger it when the
user asks about previous sessions, past decisions, unresolved bugs, what was already done,
what's still pending, or invokes `/qiju-search`.

## Shape output with qiju's own flags

NEVER pipe `qiju` output through `python`, `jq`, `awk`, or `sed`. `qiju search` already
emits exactly the shape you need — ask it for that shape:

- `--fields a,b,c` — keep only these fields, e.g. `--fields title,ts,next_steps`.
- `--format json|jsonl|summary|table|actions` — pick the rendering. `summary` is one line
  per record; `table` is columnar; `actions` rolls up open next steps as a checklist.
- `--ids-only` — return just ids (plus project/title) for a follow-up `qiju show <id>`.
- `--limit N` — cap the number of results.

Examples:

```bash
qiju search --scope current_project --query "auth cookie" --format summary
qiju search --scope current_project --fields title,ts --limit 5
qiju search --scope current_project --ids-only --query "deploy"
```

## Confirm the time range before a wide search

Infer the query's time span and act accordingly:

- Clearly recent ("yesterday", "this week"): just search.
- Open-ended ("everything I've worked on") or clearly older than ~14 days (reaching into
  the long/archive tiers): CONFIRM the intended range with the user before running the
  wide search, so you don't dump the entire history unasked.

Translate plain time phrases into bounds: "since Monday" → `--since`, "before March" →
`--until`. Pass ISO dates, e.g. `--since 2026-06-01 --until 2026-06-08`.

## Pending / open action items

When the user asks "what's pending?" or "what are the open action items?", roll up the
outstanding next steps:

```bash
qiju search --scope current_project --format actions
```

## Scope

Default to `--scope current_project`. Widen to `--scope all` only for cross-project
questions.

```bash
qiju search --scope current_project --query "<terms>"
```

## Two-phase retrieval

`qiju search` = **Phase 1: candidate identification.** Finds records and prints ids in
`<uuid>:N` form. Use `--ids-only` or `--format summary` for a cheap candidate manifest:

```bash
qiju search --scope current_project --query "deploy" --ids-only   # Phase 1: candidate ids
```

`qiju show <uuid>:N` = **Phase 2: hydrate.** Fetches the full body of the chosen record:

```bash
qiju show "<uuid>:N"   # Phase 2: hydrate one record
```

**id-format rule:** ids are always `<uuid>:N`. Pass the id to `qiju show` EXACTLY as
`qiju search` prints it, INCLUDING the `:N` suffix. A bare UUID (no `:N`) returns
'record not found'.

**bare-UUID routing:** if you only hold a bare UUID (e.g. copied from a record-body
cross-reference), do NOT call `qiju show` with it — run `qiju search` first to recover
the full `<uuid>:N` id. Never strip or guess `:N`.

{QIJU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}
"""


def _skill_md(name: str, description: str, body: str) -> str:
    """Render a SKILL.md with name+description frontmatter (Claude/Codex/Kiro format)."""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body.strip()}\n"


class AgentDetectionError(ValueError):
    pass


@dataclass
class InitResult:
    mode: str
    host: str
    project: str | None
    project_root: str | None
    qiju_home: str
    files: list[str]
    messages: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "host": self.host,
            "project": self.project,
            "project_root": self.project_root,
            "qiju_home": self.qiju_home,
            "files": self.files,
            "messages": self.messages,
        }


def canonical_agent(agent: str | None) -> str | None:
    if not agent:
        return None
    normalized = agent.strip().lower().replace("_", "-")
    aliases = {
        "claude-code": "claude",
        "claude-cli": "claude",
        "claude": "claude",
        "kiro-cli": "kiro",
        "kiro": "kiro",
        "codex-desktop": "codex",
        "codex-cli": "codex",
        "codex": "codex",
        "cursor": "cursor",
    }
    resolved = aliases.get(normalized, normalized)
    if resolved not in KNOWN_AGENTS:
        raise AgentDetectionError(f"unsupported agent: {agent}")
    return resolved


def parse_hosts(value: str | None) -> tuple[str, ...]:
    """Expand a --host value into canonical agent names.

    Accepts "all", a single host or alias, or a comma-separated list. Returns an
    empty tuple for an empty/None value so callers can fall back to auto-detection.
    """
    if not value:
        return ()
    if value.strip().lower() == "all":
        return KNOWN_AGENTS
    hosts: list[str] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        host = canonical_agent(part)
        if host not in hosts:
            hosts.append(host)
    return tuple(hosts)


def detect_current_agent(project_root: Path | None = None) -> str:
    env_agent = canonical_agent(os.environ.get("QIJU_AGENT"))
    if env_agent:
        return env_agent

    strong: list[str] = []
    if os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDECODE"):
        strong.append("claude")
    if os.environ.get("KIRO_SESSION_ID") or os.environ.get("KIRO_HOME"):
        strong.append("kiro")
    if os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_HOME"):
        strong.append("codex")
    if os.environ.get("CURSOR_SESSION_ID") or os.environ.get("CURSOR_HOME"):
        strong.append("cursor")
    strong = sorted(set(strong))
    if len(strong) == 1:
        return strong[0]
    if len(strong) > 1:
        raise AgentDetectionError(f"multiple agent environments detected: {', '.join(strong)}; pass --host")

    if project_root is not None:
        weak: list[str] = []
        if (project_root / ".kiro").exists():
            weak.append("kiro")
        if (project_root / ".cursor").exists():
            weak.append("cursor")
        if (project_root / "AGENTS.md").exists():
            weak.append("codex")
        if (project_root / "CLAUDE.md").exists():
            weak.append("claude")
        weak = sorted(set(weak))
        if len(weak) == 1:
            return weak[0]

    raise AgentDetectionError("could not detect current host; run inside a supported agent or pass --host claude|kiro|codex|cursor")


def _timestamp() -> str:
    return util.utcish_now_iso().replace(":", "").replace("+", "")


def _write_file(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    if path.exists():
        shutil.copy2(path, path.with_name(f"{path.name}.bak.{_timestamp()}"))
    path.write_text(content, encoding="utf-8")
    return True


def _qiju_log_skill(agent: str) -> str:
    return _skill_md("qiju-log", QIJU_LOG_SKILL_DESCRIPTION, QIJU_LOG_BODY.format(agent=agent))


def _qiju_search_skill() -> str:
    return _skill_md("qiju-search", QIJU_SEARCH_SKILL_DESCRIPTION, QIJU_SEARCH_BODY)


def _qiju_review_skill() -> str:
    return _skill_md("qiju-review", QIJU_REVIEW_SKILL_DESCRIPTION, QIJU_REVIEW_BODY)


def ensure_qiju_home() -> list[str]:
    home = paths_mod.qiju_home()
    files: list[str] = []
    for directory in ("long", "archive", "adapters", "agents"):
        path = home / directory
        path.mkdir(parents=True, exist_ok=True)
        files.append(str(path))
    return files


def init_global_agent(agent: str) -> tuple[list[str], list[str]]:
    files = ensure_qiju_home()
    messages: list[str] = []
    home = paths_mod.qiju_home()

    if agent == "claude":
        claude_home = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
        log_skill = _qiju_log_skill("claude")
        search_skill = _qiju_search_skill()
        review_skill = _qiju_review_skill()
        targets = {
            claude_home / "skills" / "qiju-log" / "SKILL.md": log_skill,
            claude_home / "skills" / "qiju-search" / "SKILL.md": search_skill,
            claude_home / "skills" / "qiju-review" / "SKILL.md": review_skill,
            home / "agents" / "claude-qiju-log-skill.md": log_skill,
            home / "agents" / "claude-qiju-search-skill.md": search_skill,
            home / "agents" / "claude-qiju-review-skill.md": review_skill,
        }
    elif agent == "kiro":
        kiro_home = Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser()
        log_skill = _qiju_log_skill("kiro")
        search_skill = _qiju_search_skill()
        review_skill = _qiju_review_skill()
        targets = {
            kiro_home / "skills" / "qiju-log" / "SKILL.md": log_skill,
            kiro_home / "skills" / "qiju-search" / "SKILL.md": search_skill,
            kiro_home / "skills" / "qiju-review" / "SKILL.md": review_skill,
            home / "agents" / "kiro-qiju-log-skill.md": log_skill,
            home / "agents" / "kiro-qiju-search-skill.md": search_skill,
            home / "agents" / "kiro-qiju-review-skill.md": review_skill,
        }
    elif agent == "codex":
        agent_home = Path(os.environ.get("AGENT_HOME", "~")).expanduser()
        log_skill = _qiju_log_skill("codex")
        search_skill = _qiju_search_skill()
        review_skill = _qiju_review_skill()
        targets = {
            agent_home / ".agents" / "skills" / "qiju-log" / "SKILL.md": log_skill,
            agent_home / ".agents" / "skills" / "qiju-search" / "SKILL.md": search_skill,
            agent_home / ".agents" / "skills" / "qiju-review" / "SKILL.md": review_skill,
            home / "agents" / "codex-qiju-log-skill.md": log_skill,
            home / "agents" / "codex-qiju-search-skill.md": search_skill,
            home / "agents" / "codex-qiju-review-skill.md": review_skill,
        }
    elif agent == "cursor":
        cursor_home = Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser()
        log_skill = _qiju_log_skill("cursor")
        search_skill = _qiju_search_skill()
        review_skill = _qiju_review_skill()
        targets = {
            cursor_home / "skills" / "qiju-log" / "SKILL.md": log_skill,
            cursor_home / "skills" / "qiju-search" / "SKILL.md": search_skill,
            cursor_home / "skills" / "qiju-review" / "SKILL.md": review_skill,
            home / "agents" / "cursor-qiju-log-skill.md": log_skill,
            home / "agents" / "cursor-qiju-search-skill.md": search_skill,
            home / "agents" / "cursor-qiju-review-skill.md": review_skill,
        }
    else:  # pragma: no cover
        raise AgentDetectionError(f"unsupported agent: {agent}")

    for path, content in targets.items():
        _write_file(path, content)
        files.append(str(path))

    messages.append(f"global {agent} Qiju integration enabled")
    return sorted(dict.fromkeys(files)), messages


def add_git_info_exclude(project_root: Path) -> str | None:
    exclude = project_root / ".git" / "info" / "exclude"
    if not exclude.exists():
        return None
    content = exclude.read_text(encoding="utf-8")
    if ".qiju/" not in content:
        exclude.write_text(content.rstrip() + "\n.qiju/\n", encoding="utf-8")
    return str(exclude)


def init_project_qiju(qiju_paths: paths_mod.QijuPaths, agent: str) -> list[str]:
    paths_mod.ensure_base_dirs(qiju_paths)
    files = [str(qiju_paths.project_qiju_dir)]
    if not qiju_paths.short_jsonl.exists():
        qiju_paths.short_jsonl.write_text("", encoding="utf-8")
        files.append(str(qiju_paths.short_jsonl))

    config_path = qiju_paths.project_qiju_dir / "config.json"
    now = util.utcish_now_iso()
    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except json.JSONDecodeError:
            pass
    enabled_agents = set()
    for existing_agent in existing.get("enabled_agents", []):
        if isinstance(existing_agent, str):
            enabled_agents.add(existing_agent)
    enabled_agents.add(agent)
    config = {
        "schema_version": INIT_SCHEMA_VERSION,
        "project": qiju_paths.project,
        "qiju_home": str(qiju_paths.home),
        "enabled_agents": sorted(enabled_agents),
        "default_agent": existing.get("default_agent", agent),
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    _write_file(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    files.append(str(config_path))

    exclude = add_git_info_exclude(qiju_paths.project_root)
    if exclude:
        files.append(exclude)
    return files


def init_local_agent(agent: str, *, project: str | None = None, cwd: str | Path | None = None) -> tuple[paths_mod.QijuPaths, list[str], list[str]]:
    qiju_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    files = init_project_qiju(qiju_paths, agent)
    messages: list[str] = []

    if agent == "claude":
        skills_dir = qiju_paths.project_root / ".claude" / "skills"
        log_skill = skills_dir / "qiju-log" / "SKILL.md"
        search_skill = skills_dir / "qiju-search" / "SKILL.md"
        review_skill = skills_dir / "qiju-review" / "SKILL.md"
        _write_file(log_skill, _qiju_log_skill("claude"))
        _write_file(search_skill, _qiju_search_skill())
        _write_file(review_skill, _qiju_review_skill())
        files.extend([str(log_skill), str(search_skill), str(review_skill)])
    elif agent == "kiro":
        skills_dir = qiju_paths.project_root / ".kiro" / "skills"
        log_skill = skills_dir / "qiju-log" / "SKILL.md"
        search_skill = skills_dir / "qiju-search" / "SKILL.md"
        review_skill = skills_dir / "qiju-review" / "SKILL.md"
        _write_file(log_skill, _qiju_log_skill("kiro"))
        _write_file(search_skill, _qiju_search_skill())
        _write_file(review_skill, _qiju_review_skill())
        files.extend([str(log_skill), str(search_skill), str(review_skill)])
    elif agent == "codex":
        skills_dir = qiju_paths.project_root / ".agents" / "skills"
        log_skill = skills_dir / "qiju-log" / "SKILL.md"
        search_skill = skills_dir / "qiju-search" / "SKILL.md"
        review_skill = skills_dir / "qiju-review" / "SKILL.md"
        _write_file(log_skill, _qiju_log_skill("codex"))
        _write_file(search_skill, _qiju_search_skill())
        _write_file(review_skill, _qiju_review_skill())
        files.extend([str(log_skill), str(search_skill), str(review_skill)])
    elif agent == "cursor":
        skills_dir = qiju_paths.project_root / ".cursor" / "skills"
        log_skill = skills_dir / "qiju-log" / "SKILL.md"
        search_skill = skills_dir / "qiju-search" / "SKILL.md"
        review_skill = skills_dir / "qiju-review" / "SKILL.md"
        _write_file(log_skill, _qiju_log_skill("cursor"))
        _write_file(search_skill, _qiju_search_skill())
        _write_file(review_skill, _qiju_review_skill())
        files.extend([str(log_skill), str(search_skill), str(review_skill)])
    else:  # pragma: no cover
        raise AgentDetectionError(f"unsupported agent: {agent}")

    messages.append(f"local {agent} Qiju integration enabled for {qiju_paths.project}")
    return qiju_paths, sorted(dict.fromkeys(files)), messages


def init_qiju(
    *,
    mode: str,
    agent: str | None = None,
    project: str | None = None,
    cwd: str | Path | None = None,
) -> InitResult:
    if mode not in {"local", "global"}:
        raise ValueError("mode must be local or global")

    project_root = paths_mod.project_root(cwd) if mode == "local" else None
    resolved_agent = canonical_agent(agent) if agent else detect_current_agent(project_root)

    if mode == "global":
        files, messages = init_global_agent(resolved_agent)
        return InitResult(
            mode=mode,
            host=resolved_agent,
            project=None,
            project_root=None,
            qiju_home=str(paths_mod.qiju_home()),
            files=files,
            messages=messages,
        )

    qiju_paths, files, messages = init_local_agent(resolved_agent, project=project, cwd=cwd)
    return InitResult(
        mode=mode,
        host=resolved_agent,
        project=qiju_paths.project,
        project_root=str(qiju_paths.project_root),
        qiju_home=str(qiju_paths.home),
        files=files,
        messages=messages,
    )
