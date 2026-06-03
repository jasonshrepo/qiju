from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "allowlist.json"


@dataclass
class Allowlist:
    exact: set[str]
    regexes: list[re.Pattern[str]]

    def matches(self, value: str) -> bool:
        if value in self.exact:
            return True
        return any(pattern.search(value) for pattern in self.regexes)


@lru_cache(maxsize=None)
def _load_allowlist_cached(config_path: Path) -> tuple[frozenset[str], tuple[re.Pattern[str], ...]]:
    if not config_path.exists():
        return frozenset(), ()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    exact = frozenset(data.get("exact", []))
    regexes = tuple(re.compile(pattern) for pattern in data.get("regex", []))
    return exact, regexes


def load_allowlist(path: Path | None = None) -> Allowlist:
    config_path = path or DEFAULT_CONFIG
    exact, regexes = _load_allowlist_cached(config_path)
    return Allowlist(exact=set(exact), regexes=list(regexes))
