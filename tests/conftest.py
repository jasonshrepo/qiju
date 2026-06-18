from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def qiju_env(tmp_path, monkeypatch):
    home = tmp_path / "qiju-home"
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.setenv("QIJU_HOME", str(home))
    return {"home": home, "project": project}


def sample_entry(**overrides):
    entry = {
        "schema_version": 2,
        "id": "session-1:1",
        "ts": "2026-05-31T10:00:00+10:00",
        "project": "repo",
        "agent": "claude-code",
        "source": "manual",
        "title": "Security fixes",
        "tags": ["security", "mcp"],
        "search_terms": ["auth_cookie_expired", "CORS"],
        "next_steps": ["rename auth_cookie_expired"],
        "redactions": [],
        "body_md": "Fixed an auth cookie issue and CORS policy.",
    }
    entry.update(overrides)
    return entry


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path
