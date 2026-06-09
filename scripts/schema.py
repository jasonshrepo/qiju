from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from . import util
except ImportError:  # pragma: no cover
    import util  # type: ignore


SCHEMA_VERSION = 2
VALID_SOURCES = ("manual", "agent")
REQUIRED_FIELDS = (
    "schema_version",
    "id",
    "ts",
    "project",
    "agent",
    "source",
    "title",
    "tags",
    "search_terms",
    "next_steps",
    "redactions",
    "body_md",
)


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    expected: type


FIELD_SPECS = {
    "schema_version": FieldSpec("schema_version", int),
    "id": FieldSpec("id", str),
    "ts": FieldSpec("ts", str),
    "project": FieldSpec("project", str),
    "agent": FieldSpec("agent", str),
    "source": FieldSpec("source", str),
    "title": FieldSpec("title", str),
    "tags": FieldSpec("tags", list),
    "search_terms": FieldSpec("search_terms", list),
    "next_steps": FieldSpec("next_steps", list),
    "redactions": FieldSpec("redactions", list),
    "body_md": FieldSpec("body_md", str),
}


def validate(entry: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise ValidationError(f"missing required fields: {', '.join(missing)}")

    errors: list[str] = []
    for name, spec in FIELD_SPECS.items():
        if not isinstance(entry.get(name), spec.expected):
            errors.append(f"{name} must be {spec.expected.__name__}")

    for name in ("tags", "search_terms", "next_steps"):
        values = entry.get(name)
        if isinstance(values, list) and not all(isinstance(value, str) for value in values):
            errors.append(f"{name} must contain only strings")

    redactions = entry.get("redactions")
    if isinstance(redactions, list) and not all(isinstance(value, dict) for value in redactions):
        errors.append("redactions must contain only objects")

    # A string ts must be a parseable ISO 8601 datetime. (Only check strings so we
    # don't emit both the type error above and a parse error for the same field.)
    ts = entry.get("ts")
    if isinstance(ts, str) and util.try_parse_iso(ts) is None:
        errors.append("ts must be an ISO 8601 datetime")

    if entry.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    if entry.get("source") not in VALID_SOURCES:
        errors.append(f"source must be one of: {', '.join(VALID_SOURCES)}")

    if not str(entry.get("id", "")).strip():
        errors.append("id cannot be empty")

    if not str(entry.get("project", "")).strip():
        errors.append("project cannot be empty")

    if not str(entry.get("agent", "")).strip():
        errors.append("agent cannot be empty")

    if errors:
        raise ValidationError("; ".join(errors))

    return entry


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    normalized.setdefault("schema_version", SCHEMA_VERSION)
    normalized.setdefault("agent", "unknown")
    normalized.setdefault("tags", [])
    normalized.setdefault("search_terms", [])
    normalized.setdefault("next_steps", [])
    normalized.setdefault("redactions", [])
    normalized.setdefault("body_md", "")
    normalized.setdefault("title", "")
    return normalized
