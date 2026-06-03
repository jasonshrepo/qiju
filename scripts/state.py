from __future__ import annotations

from datetime import timedelta
from pathlib import Path

try:
    from . import paths as paths_mod, storage, util
except ImportError:  # pragma: no cover
    import paths as paths_mod  # type: ignore
    import storage  # type: ignore
    import util  # type: ignore


def _date(entry: dict) -> str:
    return str(entry.get("ts", ""))[:10]


def _escape_table(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _active_decisions(entries: list[dict]) -> list[str]:
    decisions: list[str] = []
    for entry in entries:
        tags = {str(tag).lower() for tag in entry.get("tags", [])}
        body = str(entry.get("body_md", ""))
        if tags.intersection({"decision", "decisions", "architecture", "adr"}):
            decisions.append(f"- {_date(entry)} — {entry.get('title', '')}")
            continue
        for line in body.splitlines():
            if line.lower().startswith("decision:"):
                decisions.append(f"- {_date(entry)} — {line.split(':', 1)[1].strip()}")
    return decisions


def build_state_markdown(project: str, entries: list[dict], *, generated_ts: str | None = None) -> str:
    generated_ts = generated_ts or util.utcish_now_iso()
    sorted_entries = sorted(entries, key=lambda item: str(item.get("ts", "")), reverse=True)
    cutoff = util.parse_iso(generated_ts) - timedelta(days=30)

    open_items: list[str] = []
    seen_items: set[str] = set()
    for entry in sorted_entries:
        try:
            if util.parse_iso(str(entry.get("ts"))) < cutoff:
                continue
        except Exception:
            continue
        for item in entry.get("next_steps", []):
            text = str(item).strip()
            if not text or text in seen_items:
                continue
            seen_items.add(text)
            open_items.append(f"- [ ] {text} (from: {_date(entry)} \"{entry.get('title', '')}\")")

    decisions = _active_decisions(sorted_entries)
    lines = [
        f"# Kedu State — {project}",
        f"Generated: {generated_ts}",
        "",
        "## Open Items",
    ]
    lines.extend(open_items or ["_No open items from recent entries._"])
    lines.extend(["", "## Active Decisions"])
    lines.extend(decisions or ["_No active decisions detected._"])
    lines.extend(["", "## Entry Index", "| Date | Title | Agent | Source | ID |", "|------|-------|-------|--------|----|"])
    for entry in sorted_entries:
        lines.append(
            f"| {_date(entry)} | {_escape_table(entry.get('title', ''))} | "
            f"{_escape_table(entry.get('agent', 'unknown'))} | "
            f"{_escape_table(entry.get('source', ''))} | `{_escape_table(entry.get('id', ''))}` |"
        )
    lines.append("")
    return "\n".join(lines)


def rebuild_state(project: str | None = None, cwd: str | Path | None = None) -> Path:
    kedu_paths = paths_mod.resolve_paths(project=project, cwd=cwd)
    paths_mod.ensure_base_dirs(kedu_paths)
    entries = storage.read_project_entries(kedu_paths, include_short=True)
    markdown = build_state_markdown(kedu_paths.project, entries)
    util.write_text_atomic(kedu_paths.state_md, markdown)
    return kedu_paths.state_md
