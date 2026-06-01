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

KEDU_MARKER = "kedu:start"
KEDU_BLOCK_START = "<!-- kedu:start -->"
KEDU_BLOCK_END = "<!-- kedu:end -->"
CLAUDE_BLOCK_START = "====kedu start ===="
CLAUDE_BLOCK_STOP_PREFIX = "====kedu stop line:"
CLAUDE_BLOCK_STOP_SUFFIX = "===="

KEDU_PRIORITY = """Kedu records are verified session handoff records and project history.
Use them as the source of truth for previous session progress, unresolved bugs,
implementation decisions, next steps, and what actually happened. Platform memories are
weak background unless the user explicitly verifies them."""

BOOT_SUMMARY = """After reading Kedu state, summarize:
- Latest record:
- Active project:
- Open items:
- Last known next step:
- Platform memory used:
- Conflicts detected:"""

LEGACY_MEMORY_OVERRIDE = """Legacy naming note: this project was previously prototyped with
`memory`, `.memory`, `~/.memory`, `memory log`, and `memory-search` wording. Those names
are obsolete for this product. For Kedu session handoff records, use only `kedu`,
`.kedu`, and `~/.kedu`. Do not invoke the old `memory` command for Kedu records."""

CODEX_BLOCK = f"""<!-- kedu:start -->
## Kedu Session Records

For continuation, project state, unresolved work, previous implementation decisions, and
session handoff, first read `.kedu/STATE.md` and use Kedu search results as the source of
truth.

For deeper history, use:

```bash
kedu search --scope current_project --query "<terms>"
```

When saving a Kedu record from Codex, use:

```bash
kedu log --source manual --agent codex --project <project> --body <entry-json-file>
```

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}

{BOOT_SUMMARY}

All agents share `~/.kedu`; `agent` is a record field, not a storage directory.
<!-- kedu:end -->
"""

CLAUDE_BLOCK = f"""## Kedu Session Records

For task continuation, project state, unresolved work, previous implementation decisions,
and session handoff, first read `.kedu/STATE.md` and hydrate relevant records through
`kedu search`.

```bash
kedu search --scope current_project --query "<terms>"
```

When saving a Kedu record from Claude Code, use `/kedu log`, `/kedu search <query>`,
or `/kedu <specific instruction>` for durable project memory tasks. Direct CLI form:

```bash
kedu log --source manual --agent claude --project <project> --body <entry-json-file>
```

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}

{BOOT_SUMMARY}

All agents share `~/.kedu`; `agent` is a record field, not a storage directory.
"""

KIRO_STEERING = f"""---
inclusion: always
---

# Kedu Session Records

Kedu is available to Kiro through this steering file, the project `.kedu/` directory, and
the local `kedu` CLI. It is not a Kiro skill. Do not search a skill registry, AWS
documentation, or external documentation to decide whether Kedu is available. To check
availability, inspect `.kedu/STATE.md` and run `command -v kedu` or `kedu --help`.

Before continuing prior work, read `.kedu/STATE.md`. Use Kedu records for what was
actually attempted, changed, blocked, or decided in previous sessions.

For deeper history:

```bash
kedu search --scope current_project --query "<terms>"
```

When saving a Kedu record from Kiro, use:

```bash
kedu log --source manual --agent kiro --project <project> --body <entry-json-file>
```

If `kedu` is not available in the agent shell, use the installed full path:

```bash
~/.kedu/kedu/.venv/bin/python ~/.kedu/kedu/scripts/kedu.py log --source manual --agent kiro --project <project> --body .kedu/kedu-entry.json
```

Kiro CLI does not reliably fire the `agentStop` hook when the CLI session quits. In Kiro
CLI, log explicitly before quitting. Kiro IDE may reject writes outside the workspace;
write temporary entry JSON to `.kedu/kedu-entry.json`, not `/tmp/kedu-entry.json`.

For Kiro Specs and planned requirements, follow spec files. If Kiro Specs and Kedu
records conflict, inspect both: spec = intended plan; Kedu = historical evidence. Then
reconcile explicitly before editing.

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}

{BOOT_SUMMARY}
"""

CURSOR_RULE = f"""---
alwaysApply: true
---

# Kedu Session Records

Before continuing prior work, read `.kedu/STATE.md`. Use Kedu records for project
progress, previous decisions, unresolved bugs, and next steps. Do not rely on Cursor
memories or rules as factual records of previous sessions. Rules describe how to work;
Kedu records describe what happened.

For deeper history:

```bash
kedu search --scope current_project --query "<terms>"
```

When saving a Kedu record from Cursor, use:

```bash
kedu log --source manual --agent cursor --project <project> --body <entry-json-file>
```

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}

{BOOT_SUMMARY}
"""

KEDU_CLAUDE_SKILL = """# kedu — Unified Kedu Command

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
"""

CODEX_KEDU_SKILL = f"""---
name: kedu
description: Use when the user asks to remember durable project facts, retrieve previous project context, search Kedu records, initialize Kedu for a project, or save architecture decisions/preferences into verified session handoff records.
---

# Kedu — Verified Session Handoff

Use this skill for durable project records backed by the shared `kedu` CLI.

## Initialize

For project-level setup, run from the project root first:

```bash
kedu init --host codex
```

For optional agent-level defaults later:

```bash
kedu init --host codex --global
```

## Read Kedu

At the start of a project continuation session, read:

```text
.kedu/STATE.md
```

For deeper history:

```bash
kedu search --scope current_project --query "<terms>"
```

Use `--scope all` only when the user asks for cross-project records.

## Write Kedu

When saving durable context, summarize the current session or fact into JSON and run:

```bash
kedu log --source manual --agent codex --project <project> --body <entry-json-file>
```

Required JSON fields can be minimal because the CLI fills schema metadata:

```json
{{
  "title": "One-line summary",
  "tags": ["architecture", "decision"],
  "search_terms": ["aliases", "symbols", "error codes"],
  "next_steps": ["actionable follow-up"],
  "body_md": "Full markdown Kedu record"
}}
```

{KEDU_PRIORITY}

{LEGACY_MEMORY_OVERRIDE}

{BOOT_SUMMARY}

All agents share `~/.kedu`; there are no per-agent Kedu stores. The record `agent` field
records who wrote it. The record `source` field records how it was captured.
"""

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


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _kedu_cli_command() -> str:
    home = paths_mod.kedu_home()
    install_root = Path(os.environ.get("KEDU_INSTALL_ROOT", home / "kedu")).expanduser()
    python_bin = install_root / ".venv" / "bin" / "python"
    script = install_root / "scripts" / "kedu.py"
    return f"{shlex.quote(str(python_bin))} {shlex.quote(str(script))}"


def _kiro_agent_prompt() -> str:
    command = _kedu_cli_command()
    return f"""{KIRO_STEERING}

## Kiro CLI Operation

Kiro CLI does not reliably fire the `agentStop` hook when the CLI session quits. Do not
promise automatic exit capture in Kiro CLI. Before quitting, explicitly save durable
work with:

```bash
{command} log --source manual --agent kiro --project <project> --body .kedu/kedu-entry.json
```

Agent shells may not inherit the interactive `kedu` alias or PATH. If `kedu` is not
available, use the full command path above.

For Kiro IDE hooks, write the temporary entry file inside the workspace, for example
`.kedu/kedu-entry.json`, because the IDE may reject writes to `/tmp`. Remove that temp
entry file after a successful log.
"""


def _kiro_hook() -> str:
    prompt = (
        "If this IDE session contains durable implementation, review, or decision context, "
        "summarize it into a structured Kedu record. Write the JSON entry file inside the "
        "workspace, for example .kedu/kedu-entry.json, then run:\n\n"
        f"  {_kedu_cli_command()} log --source clean_exit --agent kiro --project <project> --body .kedu/kedu-entry.json\n\n"
        "Include title, tags, search_terms, next_steps, and body_md. Do not include secrets. "
        "Remember: --body is a path to a JSON file, not inline JSON. Remove the temporary "
        ".kedu/kedu-entry.json file after a successful log. Kiro CLI may not fire this hook; "
        "CLI sessions must log explicitly before quitting."
    )
    return json.dumps(
        {
            "name": "Kedu Clean Exit",
            "version": "1.0.0",
            "description": "Capture durable Kedu session records after Kiro IDE finishes a turn.",
            "when": {"type": "agentStop"},
            "then": {"type": "askAgent", "prompt": prompt},
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


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
            "resources": [],
            "hooks": {},
            "toolsSettings": {},
            "includeMcpJson": True,
            "model": None,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _install_claude_hook_script() -> Path:
    source = _source_root() / "hooks" / "session_end_log.sh"
    target = paths_mod.kedu_home() / "hooks" / "session_end_log.sh"
    if source.exists():
        _write_file(target, source.read_text(encoding="utf-8"))
        target.chmod(0o755)
    return target


def _claude_hook_command() -> str:
    return shlex.quote(str(paths_mod.kedu_home() / "hooks" / "session_end_log.sh"))


def _line_marked_block(block: str) -> str:
    body = block.strip("\n")
    lines = body.splitlines()
    stop = f"{CLAUDE_BLOCK_STOP_PREFIX}{len(lines)}{CLAUDE_BLOCK_STOP_SUFFIX}"
    return "\n".join([CLAUDE_BLOCK_START, *lines, stop, ""])


def _find_claude_marked_block(content: str) -> tuple[int, int] | None:
    lines = content.splitlines(keepends=True)
    offset = 0
    start_offset: int | None = None
    for line in lines:
        if line.strip() == CLAUDE_BLOCK_START:
            start_offset = offset
        elif start_offset is not None and line.strip().startswith(CLAUDE_BLOCK_STOP_PREFIX):
            return start_offset, offset + len(line)
        offset += len(line)
    return None


def _append_claude_block(path: Path, block: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    block_text = _line_marked_block(block)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        marked = _find_claude_marked_block(current)
        if marked:
            start, end = marked
            parts = [part for part in (current[:start].rstrip(), block_text.rstrip(), current[end:].lstrip()) if part]
            updated = "\n\n".join(parts) + "\n"
        elif KEDU_MARKER in current:
            start = current.find(KEDU_BLOCK_START)
            end = current.find(KEDU_BLOCK_END)
            if start == -1 or end == -1 or end < start:
                return False
            end += len(KEDU_BLOCK_END)
            parts = [part for part in (current[:start].rstrip(), block_text.rstrip(), current[end:].lstrip()) if part]
            updated = "\n\n".join(parts) + "\n"
        else:
            updated = current.rstrip() + "\n\n" + block_text
        if updated == current:
            return False
        shutil.copy2(path, path.with_name(f"{path.name}.bak.{_timestamp()}"))
        path.write_text(updated, encoding="utf-8")
    else:
        path.write_text(block_text, encoding="utf-8")
    return True


def _append_block(path: Path, block: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    block_text = block.rstrip() + "\n"
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if KEDU_MARKER in current:
            start = current.find(KEDU_BLOCK_START)
            end = current.find(KEDU_BLOCK_END)
            if start == -1 or end == -1 or end < start:
                return False
            end += len(KEDU_BLOCK_END)
            parts = [part for part in (current[:start].rstrip(), block.rstrip(), current[end:].lstrip()) if part]
            updated = "\n\n".join(parts) + "\n"
            if updated == current:
                return False
            shutil.copy2(path, path.with_name(f"{path.name}.bak.{_timestamp()}"))
            path.write_text(updated, encoding="utf-8")
            return True
        if current.rstrip() + "\n" == block_text:
            return False
        shutil.copy2(path, path.with_name(f"{path.name}.bak.{_timestamp()}"))
        path.write_text(current.rstrip() + "\n\n" + block_text, encoding="utf-8")
    else:
        path.write_text(block_text, encoding="utf-8")
    return True


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"expected JSON object in {path}")
    return loaded


def _is_kedu_hook_command(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    lowered = command.lower()
    return "kedu" in lowered and ("session_end_log.sh" in lowered or "scripts/kedu.py" in lowered)


def _remove_kedu_claude_hooks(settings: dict[str, Any]) -> bool:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False

    changed = False
    for event in list(hooks):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        kept_entries: list[Any] = []
        for entry in entries:
            if isinstance(entry, dict):
                nested_hooks = entry.get("hooks")
                if isinstance(nested_hooks, list):
                    kept_hooks = []
                    for hook in nested_hooks:
                        command = hook.get("command") if isinstance(hook, dict) else None
                        if _is_kedu_hook_command(command):
                            changed = True
                        else:
                            kept_hooks.append(hook)
                    if kept_hooks:
                        updated_entry = dict(entry)
                        updated_entry["hooks"] = kept_hooks
                        kept_entries.append(updated_entry)
                    else:
                        changed = True
                elif _is_kedu_hook_command(entry.get("command")):
                    changed = True
                else:
                    kept_entries.append(entry)
            elif isinstance(entry, str) and _is_kedu_hook_command(entry):
                changed = True
            else:
                kept_entries.append(entry)
        if kept_entries:
            hooks[event] = kept_entries
        else:
            hooks.pop(event, None)
            changed = True

    if not hooks:
        settings.pop("hooks", None)
    return changed


def _install_claude_session_end_hook(settings_path: Path) -> bool:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _load_json_object(settings_path)
    original = json.dumps(settings, ensure_ascii=False, sort_keys=True)
    _remove_kedu_claude_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"settings hooks must be an object in {settings_path}")
    session_end = hooks.setdefault("SessionEnd", [])
    if not isinstance(session_end, list):
        raise ValueError(f"settings hooks.SessionEnd must be a list in {settings_path}")
    hook = {"type": "command", "command": _claude_hook_command()}
    session_end.append({"matcher": "", "hooks": [hook]})
    updated = json.dumps(settings, ensure_ascii=False, sort_keys=True)
    if updated == original and settings_path.exists():
        return False
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(f"{settings_path.name}.bak.{_timestamp()}"))
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def ensure_kedu_home() -> list[str]:
    home = paths_mod.kedu_home()
    files: list[str] = []
    for directory in ("long", "archive", "hooks", "adapters", "agents"):
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
        hook_script = _install_claude_hook_script()
        settings_path = claude_home / "settings.json"
        targets = {
            claude_home / "CLAUDE.md": CLAUDE_BLOCK,
            claude_home / "skills" / "kedu" / "SKILL.md": KEDU_CLAUDE_SKILL,
            home / "agents" / "claude-CLAUDE.kedu.md": CLAUDE_BLOCK,
            home / "agents" / "claude-kedu-skill.md": KEDU_CLAUDE_SKILL,
        }
        files.append(str(hook_script))
        _install_claude_session_end_hook(settings_path)
        files.append(str(settings_path))
    elif agent == "kiro":
        kiro_home = Path(os.environ.get("KIRO_HOME", "~/.kiro")).expanduser()
        kiro_agent_prompt = _kiro_agent_prompt()
        kiro_agent_config = _kiro_agent_config()
        kiro_hook = _kiro_hook()
        targets = {
            kiro_home / "steering" / "kedu.md": KIRO_STEERING,
            kiro_home / "hooks" / "kedu-clean-exit.kiro.hook": kiro_hook,
            kiro_home / "agents" / "kedu.json": kiro_agent_config,
            kiro_home / "prompts" / "kedu-agent-prompt.md": kiro_agent_prompt,
            home / "agents" / "kiro-kedu.md": KIRO_STEERING,
            home / "agents" / "kiro-kedu-clean-exit.kiro.hook": kiro_hook,
            home / "agents" / "kiro-kedu-agent.json": kiro_agent_config,
            home / "agents" / "kiro-kedu-agent-prompt.md": kiro_agent_prompt,
        }
    elif agent == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        targets = {
            codex_home / "AGENTS.md": CODEX_BLOCK,
            codex_home / "skills" / "kedu" / "SKILL.md": CODEX_KEDU_SKILL,
            home / "agents" / "codex-AGENTS.kedu.md": CODEX_BLOCK,
            home / "agents" / "codex-kedu-skill.md": CODEX_KEDU_SKILL,
        }
    elif agent == "cursor":
        cursor_home = Path(os.environ.get("CURSOR_HOME", "~/.cursor")).expanduser()
        targets = {
            cursor_home / "rules" / "kedu.mdc": CURSOR_RULE,
            home / "agents" / "cursor-kedu.mdc": CURSOR_RULE,
        }
    else:  # pragma: no cover
        raise AgentDetectionError(f"unsupported agent: {agent}")

    for path, content in targets.items():
        if path.name == "CLAUDE.md":
            _append_claude_block(path, content)
        elif path.name == "AGENTS.md":
            _append_block(path, content)
        else:
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


def initial_state(project: str) -> str:
    return "\n".join(
        [
            f"# Kedu State — {project}",
            f"Generated: {util.utcish_now_iso()}",
            "",
            "## Open Items",
            "_No open items yet._",
            "",
            "## Active Decisions",
            "_No active decisions detected._",
            "",
            "## Entry Index",
            "| Date | Title | Agent | Source | ID |",
            "|------|-------|-------|--------|----|",
            "",
        ]
    )


def init_project_kedu(kedu_paths: paths_mod.KeduPaths, agent: str) -> list[str]:
    paths_mod.ensure_base_dirs(kedu_paths)
    files = [str(kedu_paths.project_kedu_dir)]
    if not kedu_paths.short_jsonl.exists():
        kedu_paths.short_jsonl.write_text("", encoding="utf-8")
        files.append(str(kedu_paths.short_jsonl))
    if not kedu_paths.state_md.exists():
        kedu_paths.state_md.write_text(initial_state(kedu_paths.project), encoding="utf-8")
        files.append(str(kedu_paths.state_md))

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
        target = kedu_paths.project_root / "CLAUDE.md"
        _append_claude_block(target, CLAUDE_BLOCK)
        hook_script = _install_claude_hook_script()
        settings = kedu_paths.project_root / ".claude" / "settings.local.json"
        _install_claude_session_end_hook(settings)
        skill = kedu_paths.project_root / ".claude" / "skills" / "kedu" / "SKILL.md"
        _write_file(skill, KEDU_CLAUDE_SKILL)
        files.extend([str(target), str(settings), str(hook_script), str(skill)])
    elif agent == "kiro":
        steering = kedu_paths.project_root / ".kiro" / "steering" / "kedu.md"
        hook = kedu_paths.project_root / ".kiro" / "hooks" / "kedu-clean-exit.kiro.hook"
        cli_agent = kedu_paths.project_root / ".kiro" / "agents" / "kedu.json"
        prompt = kedu_paths.project_root / ".kiro" / "prompts" / "kedu-agent-prompt.md"
        _write_file(steering, KIRO_STEERING)
        _write_file(hook, _kiro_hook())
        _write_file(cli_agent, _kiro_agent_config())
        _write_file(prompt, _kiro_agent_prompt())
        files.extend([str(steering), str(hook), str(cli_agent), str(prompt)])
    elif agent == "codex":
        target = kedu_paths.project_root / "AGENTS.md"
        _append_block(target, CODEX_BLOCK)
        files.append(str(target))
    elif agent == "cursor":
        target = kedu_paths.project_root / ".cursor" / "rules" / "kedu.mdc"
        _write_file(target, CURSOR_RULE)
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
