from __future__ import annotations

import json
import os
import shlex
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

KEDU_PRIORITY = """Kedu records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them."""

SENSITIVE_DATA_WARNING ="""Do NOT include PII, credentials, secrets, or other sensitive
information in Kedu summaries or records. Keep following the Kedu principles for useful
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
are obsolete for this product. For Kedu session handoff records, use only `kedu`,
`.kedu`, and `~/.kedu`. Do not invoke the old `memory` command for Kedu records."""

KIRO_AGENT_BASE =f"""# Kedu Session Records

Kedu is available to Kiro through two skills, `kedu-log`
(`.kiro/skills/kedu-log/SKILL.md`) and `kedu-search`
(`.kiro/skills/kedu-search/SKILL.md`), both registered through this agent's `resources`.
The skills are the primary way to log, search, and hydrate Kedu records. The project
`.kedu/` directory and the local `kedu` CLI are also available. To check availability, run
`command -v kedu` or `kedu --help`. Do not search AWS or external documentation to decide
whether Kedu is available.

Use `kedu search` to retrieve project history. When the user asks about any specific
topic, decision, bug, tool, error, component, or term, convert the question into search
terms and run a search before answering:

```bash
kedu search --scope current_project --query "<terms>"
```

## Two-phase retrieval

`kedu search` = Phase 1: candidate identification — it finds records and prints ids in
`<uuid>:N` form. Use `--ids-only` or `--format summary` for a cheap candidate manifest.

`kedu show <uuid>:N` = Phase 2: hydrate — fetches the full body of the chosen record.

**id-format rule:** ids are always `<uuid>:N`. Pass the id to `kedu show` EXACTLY as
`kedu search` prints it, INCLUDING the `:N` suffix. A bare UUID (no `:N`) returns
'record not found'.

**bare-UUID routing:** if you only hold a bare UUID (e.g. copied from a record-body
cross-reference), do NOT call `kedu show` with it — run `kedu search` first to recover
the full `<uuid>:N` id. Never strip or guess `:N`.

When saving a Kedu record from Kiro, use:

```bash
kedu log --source manual --agent kiro --project <project> --body <entry-json-file>
```

If `kedu` is not available in the agent shell, use the installed full path:

```bash
~/.kedu/kedu/.venv/bin/python ~/.kedu/kedu/scripts/kedu.py log --source manual --agent kiro --project <project> --body .kedu/kedu-entry.json
```

Kiro does not use automatic Kedu hooks. Log explicitly before ending work. Kiro may
reject writes outside the workspace; write temporary entry JSON to
`.kedu/kedu-entry.json`, not `/tmp/kedu-entry.json`.

For Kiro Specs and planned requirements, follow spec files. If Kiro Specs and Kedu
records conflict, inspect both: spec = intended plan; Kedu = historical evidence. Then
reconcile explicitly before editing.

{KEDU_PRIORITY}

{SENSITIVE_DATA_WARNING}

{LEGACY_MEMORY_OVERRIDE}
"""

KEDU_LOG_SKILL_DESCRIPTION = (
    "Use when the user asks to save, checkpoint, or hand off durable project context, "
    "record what was done or decided, or invokes `/kedu-log`; writes a verified Kedu "
    "session handoff record."
)

KEDU_SEARCH_SKILL_DESCRIPTION = (
    "Use when the user asks about previous sessions, past decisions, unresolved bugs, "
    "what was already done, what's still pending, or invokes `/kedu-search`; retrieves "
    "Kedu records."
)

# Shared log skill body. `{agent}` is the host identity (claude, codex, kiro, ...). No
# boot/startup instruction — Kedu logs on request, not on session start.
KEDU_LOG_BODY = f"""# Save a Kedu Session Record

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
   kedu log --source manual --agent {{agent}} --project <project> --body .kedu/kedu-entry.json
   ```
4. Remove `.kedu/kedu-entry.json` after a successful log.
5. Report the returned record id.

{SENSITIVE_DATA_WARNING}

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}
"""

# Shared search skill body — host-independent (no `{agent}` token).
KEDU_SEARCH_BODY = f"""# Search Kedu Session Records

Use this skill to retrieve project history through the `kedu` CLI. Trigger it when the
user asks about previous sessions, past decisions, unresolved bugs, what was already done,
what's still pending, or invokes `/kedu-search`.

## Shape output with kedu's own flags

NEVER pipe `kedu` output through `python`, `jq`, `awk`, or `sed`. `kedu search` already
emits exactly the shape you need — ask it for that shape:

- `--fields a,b,c` — keep only these fields, e.g. `--fields title,ts,next_steps`.
- `--format json|jsonl|summary|table|actions` — pick the rendering. `summary` is one line
  per record; `table` is columnar; `actions` rolls up open next steps as a checklist.
- `--ids-only` — return just ids (plus project/title) for a follow-up `kedu show <id>`.
- `--limit N` — cap the number of results.

Examples:

```bash
kedu search --scope current_project --query "auth cookie" --format summary
kedu search --scope current_project --fields title,ts --limit 5
kedu search --scope current_project --ids-only --query "deploy"
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
kedu search --scope current_project --format actions
```

## Scope

Default to `--scope current_project`. Widen to `--scope all` only for cross-project
questions.

```bash
kedu search --scope current_project --query "<terms>"
```

## Two-phase retrieval

`kedu search` = **Phase 1: candidate identification.** Finds records and prints ids in
`<uuid>:N` form. Use `--ids-only` or `--format summary` for a cheap candidate manifest:

```bash
kedu search --scope current_project --query "deploy" --ids-only   # Phase 1: candidate ids
```

`kedu show <uuid>:N` = **Phase 2: hydrate.** Fetches the full body of the chosen record:

```bash
kedu show "<uuid>:N"   # Phase 2: hydrate one record
```

**id-format rule:** ids are always `<uuid>:N`. Pass the id to `kedu show` EXACTLY as
`kedu search` prints it, INCLUDING the `:N` suffix. A bare UUID (no `:N`) returns
'record not found'.

**bare-UUID routing:** if you only hold a bare UUID (e.g. copied from a record-body
cross-reference), do NOT call `kedu show` with it — run `kedu search` first to recover
the full `<uuid>:N` id. Never strip or guess `:N`.

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}
"""


def _skill_md(name: str, description: str, body: str) -> str:
    """Render a SKILL.md with name+description frontmatter (Claude/Codex/Kiro format)."""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body.strip()}\n"


def _cursor_rule(log_body: str, search_body: str) -> str:
    """Render a single Cursor rule combining both Kedu skill bodies.

    Cursor has no slash-command skills; only the Cursor CLI is verified (IDE is
    unverified), so both bodies live in one always-available-on-request rule.
    """
    description = (
        "Kedu session records: how to save durable project context and how to search "
        "previous sessions, decisions, and pending work through the kedu CLI."
    )
    return (
        f"---\ndescription: {description}\nalwaysApply: false\n---\n\n"
        f"{log_body.strip()}\n\n---\n\n{search_body.strip()}\n"
    )


class AgentDetectionError(ValueError):
    pass


@dataclass
class InitResult:
    mode: str
    host: str
    project: str | None
    project_root: str | None
    kedu_home: str
    files: list[str]
    messages: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "host": self.host,
            "project": self.project,
            "project_root": self.project_root,
            "kedu_home": self.kedu_home,
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
    env_agent = canonical_agent(os.environ.get("KEDU_AGENT"))
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


def _kedu_cli_command() -> str:
    home = paths_mod.kedu_home()
    install_root = Path(os.environ.get("KEDU_INSTALL_ROOT", home / "kedu")).expanduser()
    python_bin = install_root / ".venv" / "bin" / "python"
    script = install_root / "scripts" / "kedu.py"
    return f"{shlex.quote(str(python_bin))} {shlex.quote(str(script))}"


def _kiro_agent_prompt() -> str:
    command = _kedu_cli_command()
    return f"""{KIRO_AGENT_BASE}

## Kiro CLI Operation

Kiro does not use automatic Kedu hooks. Do not promise automatic exit capture. Before
quitting or when asked to save progress, explicitly save durable work with:

```bash
{command} log --source manual --agent kiro --project <project> --body .kedu/kedu-entry.json
```

Agent shells may not inherit the interactive `kedu` alias or PATH. If `kedu` is not
available, use the full command path above.

Write the temporary entry file inside the workspace, for example
`.kedu/kedu-entry.json`, because Kiro may reject writes to `/tmp`. Remove that temp entry
file after a successful log.
"""


def _kiro_agent_config() -> str:
    return json.dumps(
        {
            "name": "kedu",
            "description": "Default Kiro agent with Kedu session handoff records enabled.",
            "prompt": _kiro_agent_prompt(),
            "mcpServers": {},
            "tools": [
                "read",
                "write",
                "shell",
                "aws",
                "report",
                "introspect",
                "knowledge",
                "thinking",
                "todo",
                "delegate",
                "grep",
                "glob",
            ],
            "toolAliases": {},
            "allowedTools": [],
            "resources": [
                "skill://.kiro/skills/*/SKILL.md",
                "skill://~/.kiro/skills/*/SKILL.md",
            ],
            "hooks": {},
            "toolsSettings": {},
            "includeMcpJson": True,
            "model": None,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _kedu_log_skill(agent: str) -> str:
    return _skill_md("kedu-log", KEDU_LOG_SKILL_DESCRIPTION, KEDU_LOG_BODY.format(agent=agent))


def _kedu_search_skill() -> str:
    return _skill_md("kedu-search", KEDU_SEARCH_SKILL_DESCRIPTION, KEDU_SEARCH_BODY)


def ensure_kedu_home() -> list[str]:
    home = paths_mod.kedu_home()
    files: list[str] = []
    for directory in ("long", "archive", "adapters", "agents"):
        path = home / directory
        path.mkdir(parents=True, exist_ok=True)
        files.append(str(path))
    return files


def init_global_agent(agent: str) -> tuple[list[str], list[str]]:
    files = ensure_kedu_home()
    messages: list[str] = []
    home = paths_mod.kedu_home()

    if agent == "claude":
        claude_home = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
        log_skill = _kedu_log_skill("claude")
        search_skill = _kedu_search_skill()
        targets = {
            claude_home / "skills" / "kedu-log" / "SKILL.md": log_skill,
            claude_home / "skills" / "kedu-search" / "SKILL.md": search_skill,
            home / "agents" / "claude-kedu-log-skill.md": log_skill,
            home / "agents" / "claude-kedu-search-skill.md": search_skill,
        }
    elif agent == "kiro":
        kiro_home = Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser()
        kiro_agent_config = _kiro_agent_config()
        log_skill = _kedu_log_skill("kiro")
        search_skill = _kedu_search_skill()
        targets = {
            kiro_home / "agents" / "kedu.json": kiro_agent_config,
            kiro_home / "skills" / "kedu-log" / "SKILL.md": log_skill,
            kiro_home / "skills" / "kedu-search" / "SKILL.md": search_skill,
            home / "agents" / "kiro-kedu-agent.json": kiro_agent_config,
            home / "agents" / "kiro-kedu-log-skill.md": log_skill,
            home / "agents" / "kiro-kedu-search-skill.md": search_skill,
        }
    elif agent == "codex":
        agent_home = Path(os.environ.get("AGENT_HOME", "~")).expanduser()
        log_skill = _kedu_log_skill("codex")
        search_skill = _kedu_search_skill()
        targets = {
            agent_home / ".agents" / "skills" / "kedu-log" / "SKILL.md": log_skill,
            agent_home / ".agents" / "skills" / "kedu-search" / "SKILL.md": search_skill,
            home / "agents" / "codex-kedu-log-skill.md": log_skill,
            home / "agents" / "codex-kedu-search-skill.md": search_skill,
        }
    elif agent == "cursor":
        cursor_home = Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser()
        cursor_rule = _cursor_rule(KEDU_LOG_BODY.format(agent="cursor"), KEDU_SEARCH_BODY)
        targets = {
            cursor_home / "rules" / "kedu.mdc": cursor_rule,
            home / "agents" / "cursor-kedu.mdc": cursor_rule,
        }
    else:  # pragma: no cover
        raise AgentDetectionError(f"unsupported agent: {agent}")

    for path, content in targets.items():
        _write_file(path, content)
        files.append(str(path))

    messages.append(f"global {agent} Kedu integration enabled")
    return sorted(dict.fromkeys(files)), messages


def add_git_info_exclude(project_root: Path) -> str | None:
    exclude = project_root / ".git" / "info" / "exclude"
    if not exclude.exists():
        return None
    content = exclude.read_text(encoding="utf-8")
    if ".kedu/" not in content:
        exclude.write_text(content.rstrip() + "\n.kedu/\n", encoding="utf-8")
    return str(exclude)


def init_project_kedu(kedu_paths: paths_mod.KeduPaths, agent: str) -> list[str]:
    paths_mod.ensure_base_dirs(kedu_paths)
    files = [str(kedu_paths.project_kedu_dir)]
    if not kedu_paths.short_jsonl.exists():
        kedu_paths.short_jsonl.write_text("", encoding="utf-8")
        files.append(str(kedu_paths.short_jsonl))

    config_path = kedu_paths.project_kedu_dir / "config.json"
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
        "project": kedu_paths.project,
        "kedu_home": str(kedu_paths.home),
        "enabled_agents": sorted(enabled_agents),
        "default_agent": existing.get("default_agent", agent),
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    _write_file(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    files.append(str(config_path))

    exclude = add_git_info_exclude(kedu_paths.project_root)
    if exclude:
        files.append(exclude)
    return files


def init_local_agent(agent: str, *, project: str | None = None, cwd: str | Path | None = None) -> tuple[paths_mod.KeduPaths, list[str], list[str]]:
    kedu_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    files = init_project_kedu(kedu_paths, agent)
    messages: list[str] = []

    if agent == "claude":
        skills_dir = kedu_paths.project_root / ".claude" / "skills"
        log_skill = skills_dir / "kedu-log" / "SKILL.md"
        search_skill = skills_dir / "kedu-search" / "SKILL.md"
        _write_file(log_skill, _kedu_log_skill("claude"))
        _write_file(search_skill, _kedu_search_skill())
        files.extend([str(log_skill), str(search_skill)])
    elif agent == "kiro":
        cli_agent = kedu_paths.project_root / ".kiro" / "agents" / "kedu.json"
        skills_dir = kedu_paths.project_root / ".kiro" / "skills"
        log_skill = skills_dir / "kedu-log" / "SKILL.md"
        search_skill = skills_dir / "kedu-search" / "SKILL.md"
        _write_file(cli_agent, _kiro_agent_config())
        _write_file(log_skill, _kedu_log_skill("kiro"))
        _write_file(search_skill, _kedu_search_skill())
        files.extend([str(cli_agent), str(log_skill), str(search_skill)])
    elif agent == "codex":
        skills_dir = kedu_paths.project_root / ".agents" / "skills"
        log_skill = skills_dir / "kedu-log" / "SKILL.md"
        search_skill = skills_dir / "kedu-search" / "SKILL.md"
        _write_file(log_skill, _kedu_log_skill("codex"))
        _write_file(search_skill, _kedu_search_skill())
        files.extend([str(log_skill), str(search_skill)])
    elif agent == "cursor":
        target = kedu_paths.project_root / ".cursor" / "rules" / "kedu.mdc"
        _write_file(target, _cursor_rule(KEDU_LOG_BODY.format(agent="cursor"), KEDU_SEARCH_BODY))
        files.append(str(target))
    else:  # pragma: no cover
        raise AgentDetectionError(f"unsupported agent: {agent}")

    messages.append(f"local {agent} Kedu integration enabled for {kedu_paths.project}")
    return kedu_paths, sorted(dict.fromkeys(files)), messages


def init_kedu(
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
            kedu_home=str(paths_mod.kedu_home()),
            files=files,
            messages=messages,
        )

    kedu_paths, files, messages = init_local_agent(resolved_agent, project=project, cwd=cwd)
    return InitResult(
        mode=mode,
        host=resolved_agent,
        project=kedu_paths.project,
        project_root=str(kedu_paths.project_root),
        kedu_home=str(kedu_paths.home),
        files=files,
        messages=messages,
    )
