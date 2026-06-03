from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from . import allowlist as allowlist_mod
except ImportError:  # pragma: no cover
    import allowlist as allowlist_mod  # type: ignore


RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "redaction_rules.json"
TOKEN_RE = re.compile(r"[A-Za-z0-9/+_.=:-]{20,}")


@dataclass(frozen=True)
class RedactionRule:
    type: str
    pattern: re.Pattern[str]
    placeholder: str


@lru_cache(maxsize=None)
def _load_rules_cached(config_path: Path) -> tuple[RedactionRule, ...]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    rules: list[RedactionRule] = []
    for item in data:
        rules.append(
            RedactionRule(
                type=item["type"],
                # JSON strings cannot embed inline regex flags; [\s\S] matches any char
                # including newlines as a portable alternative to re.DOTALL.
                pattern=re.compile(item["pattern"]),
                placeholder=item["placeholder"],
            )
        )
    return tuple(rules)


def load_rules(path: Path | None = None) -> list[RedactionRule]:
    config_path = path or RULES_PATH
    return list(_load_rules_cached(config_path))


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _redact_string(
    value: str,
    field: str,
    rules: list[RedactionRule],
    allowlist: allowlist_mod.Allowlist,
) -> tuple[str, list[dict[str, Any]]]:
    redactions: list[dict[str, Any]] = []

    for rule in rules:
        def replace(match: re.Match[str], _rule: RedactionRule = rule) -> str:
            text = match.group(0)
            if allowlist.matches(text):
                return text
            redactions.append(
                {
                    "field": field,
                    "type": _rule.type,
                    "start": match.start(),
                    "end": match.end(),
                    "placeholder": _rule.placeholder,
                }
            )
            return _rule.placeholder

        value = rule.pattern.sub(replace, value)

    def replace_high_entropy(match: re.Match[str]) -> str:
        text = match.group(0)
        if allowlist.matches(text):
            return text
        if shannon_entropy(text) <= 4.5:
            return text
        redactions.append(
            {
                "field": field,
                "type": "high_entropy",
                "start": match.start(),
                "end": match.end(),
                "placeholder": "[REDACTED:high_entropy]",
            }
        )
        return "[REDACTED:high_entropy]"

    value = TOKEN_RE.sub(replace_high_entropy, value)
    return value, redactions


def redact_value(
    value: Any,
    field: str,
    rules: list[RedactionRule] | None = None,
    allowlist: allowlist_mod.Allowlist | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    rules = rules if rules is not None else load_rules()
    allowlist = allowlist if allowlist is not None else allowlist_mod.load_allowlist()
    redactions: list[dict[str, Any]] = []

    if isinstance(value, str):
        return _redact_string(value, field, rules, allowlist)
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            redacted, item_redactions = redact_value(item, f"{field}[{index}]", rules, allowlist)
            result.append(redacted)
            redactions.extend(item_redactions)
        return result, redactions
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            redacted, item_redactions = redact_value(item, f"{field}.{key}", rules, allowlist)
            result[key] = redacted
            redactions.extend(item_redactions)
        return result, redactions
    return value, []


def redact_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rules = load_rules()
    allowlist = allowlist_mod.load_allowlist()
    result = dict(entry)
    all_redactions: list[dict[str, Any]] = []
    for field in ("agent", "title", "tags", "search_terms", "next_steps", "body_md"):
        redacted, redactions = redact_value(result.get(field, ""), field, rules, allowlist)
        result[field] = redacted
        all_redactions.extend(redactions)
    existing = list(result.get("redactions", []))
    result["redactions"] = existing + all_redactions
    return result, all_redactions


def replace_literal_in_entry(entry: dict[str, Any], value: str, placeholder: str) -> tuple[dict[str, Any], bool]:
    changed = False

    def replace(item: Any) -> Any:
        nonlocal changed
        if isinstance(item, str):
            if value in item:
                changed = True
                return item.replace(value, placeholder)
            return item
        if isinstance(item, list):
            return [replace(part) for part in item]
        if isinstance(item, dict):
            return {key: replace(part) for key, part in item.items()}
        return item

    result = replace(entry)
    if changed:
        result.setdefault("redactions", []).append(
            {"field": "*", "type": "retroactive", "placeholder": placeholder}
        )
    return result, changed
