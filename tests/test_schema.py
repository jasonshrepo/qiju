from __future__ import annotations

import pytest

from scripts import id_gen, paths, schema
from tests.conftest import sample_entry


def test_schema_valid_entry_passes():
    assert schema.validate(sample_entry())["id"] == "session-1:1"


def test_schema_missing_required_fields_fail():
    entry = sample_entry()
    del entry["body_md"]
    with pytest.raises(schema.ValidationError, match="missing required fields"):
        schema.validate(entry)


def test_schema_source_enum_enforced():
    with pytest.raises(schema.ValidationError, match="source must be"):
        schema.validate(sample_entry(source="auto"))


def test_normalize_entry_fills_expected_defaults():
    entry = schema.normalize_entry({"title": "Minimal entry"})

    assert isinstance(entry["schema_version"], int)
    assert entry["schema_version"] == schema.SCHEMA_VERSION
    assert isinstance(entry["agent"], str)
    assert entry["agent"] == "unknown"
    assert isinstance(entry["tags"], list)
    assert entry["tags"] == []
    assert isinstance(entry["search_terms"], list)
    assert entry["search_terms"] == []
    assert isinstance(entry["next_steps"], list)
    assert entry["next_steps"] == []
    assert isinstance(entry["redactions"], list)
    assert entry["redactions"] == []
    assert isinstance(entry["body_md"], str)
    assert entry["body_md"] == ""


def test_id_generation_is_deterministic_for_explicit_session(kedu_env):
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    assert id_gen.make_id(kedu_paths, explicit_session_uuid="abc", explicit_seq=2) == "abc:2"
