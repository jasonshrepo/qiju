from __future__ import annotations

from scripts import redact
from tests.conftest import sample_entry


def test_aws_access_key_is_redacted():
    entry, redactions = redact.redact_entry(
        sample_entry(body_md="key AKIAIOSFODNN7EXAMPLE should not persist")
    )
    assert "[REDACTED:aws_access_key]" in entry["body_md"]
    assert any(item["type"] == "aws_access_key" for item in redactions)


def test_email_is_redacted():
    entry, redactions = redact.redact_entry(sample_entry(body_md="Contact person@example.com"))
    assert "[REDACTED:email]" in entry["body_md"]
    assert any(item["type"] == "email" for item in redactions)


def test_allowlisted_commit_sha_is_not_high_entropy_redacted():
    sha = "0123456789abcdef0123456789abcdef01234567"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"commit {sha}"))
    assert sha in entry["body_md"]
    assert not any(item["type"] == "high_entropy" for item in redactions)


def test_high_entropy_token_is_redacted():
    token = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef0123456789+/"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"token {token}"))

    assert redact.shannon_entropy(token) > 4.5
    assert "[REDACTED:high_entropy]" in entry["body_md"]
    assert any(item["type"] == "high_entropy" for item in redactions)


def test_low_entropy_token_is_preserved():
    token = "aaaabbbbccccddddeeee"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"token {token}"))

    assert redact.shannon_entropy(token) <= 4.5
    assert token in entry["body_md"]
    assert not any(item["type"] == "high_entropy" for item in redactions)


def test_replace_literal_in_entry_replaces_string_field():
    entry = sample_entry(body_md="Token secret-value leaked")

    result, changed = redact.replace_literal_in_entry(entry, "secret-value", "[REDACTED:manual]")

    assert changed is True
    assert result["body_md"] == "Token [REDACTED:manual] leaked"


def test_replace_literal_in_entry_replaces_nested_list_value():
    entry = sample_entry(tags=["safe", "secret-value-tag"], search_terms=["keep"])

    result, changed = redact.replace_literal_in_entry(entry, "secret-value", "[REDACTED:manual]")

    assert changed is True
    assert result["tags"] == ["safe", "[REDACTED:manual]-tag"]
    assert result["search_terms"] == ["keep"]


def test_replace_literal_in_entry_appends_retroactive_redaction_metadata():
    entry = sample_entry(body_md="secret-value")

    result, changed = redact.replace_literal_in_entry(entry, "secret-value", "[REDACTED:manual]")

    assert changed is True
    assert result["redactions"] == [{"field": "*", "type": "retroactive", "placeholder": "[REDACTED:manual]"}]


def test_replace_literal_in_entry_no_change_returns_unmodified_entry():
    entry = sample_entry(body_md="safe content")

    result, changed = redact.replace_literal_in_entry(entry, "secret-value", "[REDACTED:manual]")

    assert changed is False
    assert result == entry
