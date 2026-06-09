from __future__ import annotations

import json
import re

import pytest

from scripts import redact, retro_redact, util
from tests.conftest import sample_entry


PII_TOKEN_PREFIX = "[REDACTED:pii:"


def test_redaction_rules_are_valid():
    data = json.loads(redact.RULES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data
    for rule in data:
        assert "type" in rule
        assert "pattern" in rule
        # Must compile without error.
        re.compile(rule["pattern"])


def test_hash_token_format_and_irreversibility():
    raw = "AKIAIOSFODNN7EXAMPLE"
    token = redact._hash_token(raw)
    assert token.startswith(PII_TOKEN_PREFIX)
    assert token.endswith("]")
    # 16 hex chars between prefix and closing bracket.
    digest = token[len(PII_TOKEN_PREFIX):-1]
    assert len(digest) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", digest)
    # The raw value never appears inside the token.
    assert raw not in token


def test_aws_access_key_is_redacted():
    raw = "AKIAIOSFODNN7EXAMPLE"
    entry, redactions = redact.redact_entry(
        sample_entry(body_md=f"key {raw} should not persist")
    )
    assert PII_TOKEN_PREFIX in entry["body_md"]
    assert raw not in entry["body_md"]
    assert any(item["type"] == "aws_access_key" for item in redactions)


def test_email_is_redacted():
    raw = "person@example.com"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"Contact {raw}"))
    assert PII_TOKEN_PREFIX in entry["body_md"]
    assert raw not in entry["body_md"]
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
    assert PII_TOKEN_PREFIX in entry["body_md"]
    assert token not in entry["body_md"]
    assert any(item["type"] == "high_entropy" for item in redactions)


def test_low_entropy_token_is_preserved():
    token = "aaaabbbbccccddddeeee"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"token {token}"))

    assert redact.shannon_entropy(token) <= 4.5
    assert token in entry["body_md"]
    assert not any(item["type"] == "high_entropy" for item in redactions)


# Each tuple is (rule_type, raw_value_that_should_be_redacted).
NEW_PATTERN_SAMPLES = [
    ("github_token", "ghp_" + "a" * 36),
    ("github_fine_grained_pat", "github_pat_" + "B" * 22 + "_extra1234"),
    ("slack_token", "xoxb-2W4X6Z8R0T-Zt9QwXyZ"),
    ("google_api_key", "AIza" + "A" * 35),
    ("stripe_key", "sk_live_" + "abcd1234EFGH5678"),
    ("openai_anthropic_key", "sk-ant-" + "A" * 24),
    ("jwt", "eyJabc123_-.eyJdef456_-.signature_part-123"),
    ("us_phone", "+1 415-555-0132"),
    ("us_ssn", "123-45-6789"),
    ("credit_card", "4111 1111 1111 1111"),
    ("ipv4", "192.168.1.100"),
]


@pytest.mark.parametrize("rule_type,raw", NEW_PATTERN_SAMPLES)
def test_new_pattern_is_redacted(rule_type, raw):
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"value: {raw} end"))
    assert PII_TOKEN_PREFIX in entry["body_md"], (rule_type, entry["body_md"])
    assert raw not in entry["body_md"], (rule_type, entry["body_md"])


def test_hashed_output_does_not_leak_raw_value_in_metadata():
    raw = "person@example.com"
    entry, redactions = redact.redact_entry(sample_entry(body_md=f"email {raw}"))

    serialized = json.dumps(entry)
    assert raw not in serialized
    for item in entry["redactions"]:
        assert raw not in json.dumps(item)
        # Metadata stores only structural fields, never the raw match.
        assert set(item).issubset({"field", "type", "start", "end", "placeholder"})
        assert item["placeholder"].startswith(PII_TOKEN_PREFIX)


# --- Retroactive (manual literal) path: unchanged behavior ---


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


# --- Blank retroactive redaction is rejected and leaves records untouched ---


def _seed_short_and_long(kedu_env):
    home = kedu_env["home"]
    project = kedu_env["project"]
    short = project / ".kedu" / "short.jsonl"
    long_file = home / "long" / "repo.jsonl"
    short.parent.mkdir(parents=True, exist_ok=True)
    long_file.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        sample_entry(id="session-1:1", body_md="first entry with content"),
        sample_entry(id="session-1:2", body_md="second entry with content"),
    ]
    for entry in entries:
        util.append_jsonl(short, entry)
        util.append_jsonl(long_file, entry)
    return short, long_file


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t\n"])
def test_blank_redaction_value_rejected_and_files_unchanged(kedu_env, blank):
    short, long_file = _seed_short_and_long(kedu_env)
    short_before = short.read_bytes()
    long_before = long_file.read_bytes()

    with pytest.raises(ValueError):
        retro_redact.redact_value_everywhere(
            value=blank,
            reason="attempted blank redaction",
            project="repo",
            cwd=kedu_env["project"],
        )

    assert short.read_bytes() == short_before
    assert long_file.read_bytes() == long_before


def test_redaction_log_reason_is_redacted(kedu_env):
    _seed_short_and_long(kedu_env)
    secret = "AKIAIOSFODNN7EXAMPLE"
    retro_redact.redact_value_everywhere(
        value="content",
        reason=f"leaked {secret} here",
        project="repo",
        cwd=kedu_env["project"],
    )
    redaction_log = kedu_env["home"] / "redaction_log.jsonl"
    raw_log = redaction_log.read_text(encoding="utf-8")
    assert secret not in raw_log
    events = util.read_jsonl(redaction_log)
    assert events
    assert secret not in events[-1]["reason"]
