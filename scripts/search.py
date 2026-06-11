from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from . import paths as paths_mod, storage, util
except ImportError:  # pragma: no cover
    import paths as paths_mod  # type: ignore
    import storage  # type: ignore
    import util  # type: ignore


def _resolve_scope(scope: str, project: str | None, cwd: str | Path | None) -> list[str]:
    current = paths_mod.project_slug(project, cwd)
    if scope == "current_project":
        return [current]
    if scope == "all":
        projects = storage.all_projects(paths_mod.kedu_home())
        return projects or [current]
    projects = [paths_mod.slugify_project(part) for part in scope.split(",") if part.strip()]
    if not projects:
        raise ValueError("scope must be current_project, all, or a comma-separated project list")
    return projects


def _entry_text(entry: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("agent", "title", "body_md"):
        parts.append(str(entry.get(field, "")))
    for field in ("tags", "search_terms", "next_steps"):
        value = entry.get(field, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    return "\n".join(parts)


def _matches_query(entry: dict[str, Any], query: str | None, regex: bool = False) -> bool:
    if not query:
        return True
    text = _entry_text(entry)
    if regex:
        return re.search(query, text, flags=re.IGNORECASE | re.MULTILINE) is not None
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return True
    return any(re.search(re.escape(term), text, flags=re.IGNORECASE) for term in terms)


def _contains_tag(entry: dict[str, Any], tags: list[str]) -> bool:
    if not tags:
        return True
    entry_tags = {str(tag).lower() for tag in entry.get("tags", [])}
    return all(tag.lower() in entry_tags for tag in tags)


def _in_time_range(entry: dict[str, Any], since: str | None, until: str | None) -> bool:
    if not since and not until:
        return True
    # A time filter is active: an entry with an unparseable ts can't satisfy a range
    # bound, so exclude it (rather than crashing). The CLI bounds stay strict via parse_iso.
    ts = util.try_parse_iso(entry.get("ts"))
    if ts is None:
        return False
    if since and ts < util.parse_iso(since):
        return False
    if until and ts > util.parse_iso(until):
        return False
    return True


def search_entries(
    *,
    scope: str = "current_project",
    query: str | None = None,
    project: str | None = None,
    cwd: str | Path | None = None,
    tags: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    source: str | None = None,
    agent: str | None = None,
    limit: int | None = None,
    ids_only: bool = False,
    regex: bool = False,
    sort: str = "ts",
    order: str = "desc",
) -> list[dict[str, Any]]:
    projects = _resolve_scope(scope, project, cwd)
    tags = tags or []
    entries: list[dict[str, Any]] = []
    for project_name in projects:
        kedu_paths = paths_mod.resolve_paths(project=project_name, cwd=cwd)
        entries.extend(storage.read_project_entries(kedu_paths))

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    reverse = order != "asc"
    for entry in sorted(entries, key=lambda item: str(item.get(sort, "")), reverse=reverse):
        entry_id = str(entry.get("id", ""))
        if entry_id in seen:
            continue
        seen.add(entry_id)
        if str(entry.get("project", "")).lower() not in projects:
            continue
        if source and entry.get("source") != source:
            continue
        if agent and entry.get("agent", "unknown") != agent:
            continue
        if not _contains_tag(entry, tags):
            continue
        if not _in_time_range(entry, since, until):
            continue
        if not _matches_query(entry, query, regex=regex):
            continue
        if ids_only:
            results.append({"id": entry_id, "project": entry.get("project"), "title": entry.get("title")})
        else:
            results.append(entry)
        if limit is not None and len(results) >= limit:
            break

    return results


def show_entry(entry_id: str, *, project: str | None = None, cwd: str | Path | None = None) -> dict[str, Any] | None:
    scope = "all" if project is None else "current_project"
    entries = search_entries(scope=scope, project=project, cwd=cwd)
    for entry in entries:
        if entry.get("id") == entry_id:
            return entry
    return None


def rollup_next_steps(entries: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Collect open next_steps across entries, newest-first, deduped.

    `entries` is expected in the order returned by search_entries (newest-first). For each
    entry, every next_steps string is collected and deduped by normalized text (strip +
    casefold), keeping the FIRST (newest) occurrence paired with its source entry. Returns
    a list of (text, source_entry) tuples.
    """
    seen: set[str] = set()
    rolled: list[tuple[str, dict[str, Any]]] = []
    for entry in entries:
        steps = entry.get("next_steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            text = str(step).strip()
            if not text:
                continue
            # Dedup key normalizes case AND collapses internal whitespace so trivially
            # reworded duplicates ("fix  bug" vs "Fix bug") roll up to one entry.
            key = " ".join(text.split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            rolled.append((text, entry))
    return rolled


def to_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, ensure_ascii=False, indent=2)
