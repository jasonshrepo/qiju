from __future__ import annotations

import json
import re
from dataclasses import dataclass
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


def load_allowlist(path: Path | None = None) -> Allowlist:
    config_path = path or DEFAULT_CONFIG
    if not config_path.exists():
        return Allowlist(exact=set(), regexes=[])
    data = json.loads(config_path.read_text(encoding="utf-8"))
    exact = set(data.get("exact", []))
    regexes = [re.compile(pattern) for pattern in data.get("regex", [])]
    return Allowlist(exact=exact, regexes=regexes)

