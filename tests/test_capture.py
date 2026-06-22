from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest

from qiju import archive, capture, maintain, paths, util
from tests.conftest import sample_entry


def test_log_writes_short_and_long(qiju_env):
    entry_id = capture.log_entry(sample_entry(), source="manual", project="repo", cwd=qiju_env["project"])
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    assert entry_id == "session-1:1"
    assert len(util.read_jsonl(qiju_paths.short_jsonl)) == 1
    assert len(util.read_jsonl(qiju_paths.long_jsonl)) == 1


def test_log_is_idempotent(qiju_env):
    entry = sample_entry()
    capture.log_entry(entry, source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(entry, source="manual", project="repo", cwd=qiju_env["project"])
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    assert len(util.read_jsonl(qiju_paths.short_jsonl)) == 1
    assert len(util.read_jsonl(qiju_paths.long_jsonl)) == 1


def test_capture_redacts_before_write(qiju_env):
    capture.log_entry(
        sample_entry(body_md="AKIAIOSFODNN7EXAMPLE"),
        source="manual",
        project="repo",
        cwd=qiju_env["project"],
    )
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    written = util.read_jsonl(qiju_paths.long_jsonl)[0]
    assert written["body_md"].startswith("[REDACTED:pii:")
    assert "AKIAIOSFODNN7EXAMPLE" not in written["body_md"]
    assert written["redactions"]


def test_capture_accepts_agent_identity(qiju_env):
    capture.log_entry(
        sample_entry(id="agent-test:1", agent="ignored"),
        source="manual",
        agent="codex",
        project="repo",
        cwd=qiju_env["project"],
    )
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    written = util.read_jsonl(qiju_paths.long_jsonl)[0]
    assert written["agent"] == "codex"


def test_agents_share_same_qiju_store(qiju_env):
    capture.log_entry(
        sample_entry(id="claude:1", agent="claude-code"),
        source="manual",
        agent="claude-code",
        project="repo",
        cwd=qiju_env["project"],
    )
    capture.log_entry(
        sample_entry(id="kiro:1", agent="kiro", title="Kiro review"),
        source="manual",
        agent="kiro",
        project="repo",
        cwd=qiju_env["project"],
    )
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    entries = util.read_jsonl(qiju_paths.long_jsonl)
    assert qiju_paths.long_jsonl == qiju_env["home"] / "long" / "repo.jsonl"
    assert {entry["agent"] for entry in entries} == {"claude-code", "kiro"}
    assert not (qiju_env["home"] / "claude-code").exists()
    assert not (qiju_env["home"] / "kiro").exists()


def test_log_continues_sequence_when_session_records_are_archived(qiju_env, monkeypatch):
    monkeypatch.setattr(maintain, "MAX_SMALL_PARTITION_AGE_DAYS", 30)
    old_entry = sample_entry(ts="2026-01-01T10:00:00+10:00")
    old_entry.pop("id")

    first_id = capture.log_entry(
        old_entry,
        source="manual",
        project="repo",
        cwd=qiju_env["project"],
        session_id="archive-session",
    )
    assert first_id == "archive-session:1"

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    maintain.maintain(
        project="repo",
        cwd=qiju_env["project"],
        now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"),
    )
    assert util.read_jsonl(qiju_paths.short_jsonl) == []
    assert util.read_jsonl(qiju_paths.long_jsonl) == []
    assert {entry["id"] for entry in archive.read_parquet(qiju_paths.archive_partition("2026-01"))} == {first_id}

    new_entry = sample_entry(title="Follow-up after archive", ts="2026-06-01T10:00:00+10:00")
    new_entry.pop("id")
    second_id = capture.log_entry(
        new_entry,
        source="manual",
        project="repo",
        cwd=qiju_env["project"],
        session_id="archive-session",
    )

    assert second_id == "archive-session:2"
    assert [entry["id"] for entry in util.read_jsonl(qiju_paths.long_jsonl)] == [second_id]


def test_concurrent_same_session_logs_get_distinct_generated_ids(qiju_env, monkeypatch):
    original_prepare_entry = capture.prepare_entry
    barrier = Barrier(2)

    def synchronized_prepare_entry(*args, **kwargs):
        entry = original_prepare_entry(*args, **kwargs)
        barrier.wait(timeout=5)
        return entry

    monkeypatch.setattr(capture, "prepare_entry", synchronized_prepare_entry)

    def write_entry(index: int) -> str:
        entry = sample_entry(title=f"Concurrent write {index}", body_md=f"Body {index}")
        entry.pop("id")
        return capture.log_entry(
            entry,
            source="manual",
            project="repo",
            cwd=qiju_env["project"],
            session_id="thread-session",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(write_entry, [1, 2]))

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    long_entries = util.read_jsonl(qiju_paths.long_jsonl)

    assert sorted(ids) == ["thread-session:1", "thread-session:2"]
    assert sorted(entry["id"] for entry in long_entries) == ["thread-session:1", "thread-session:2"]


def test_read_entry_missing_body_file(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(ValueError, match=f"body file not found: {missing}"):
        capture.read_entry(str(missing))


def test_read_entry_empty_body_file(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"body file is empty: {empty}"):
        capture.read_entry(str(empty))


def test_read_entry_invalid_json_body_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match=f"body file {bad} is not valid JSON"):
        capture.read_entry(str(bad))


def test_read_entry_non_object_body_file(tmp_path):
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match=f"body file {arr} must contain a JSON object"):
        capture.read_entry(str(arr))


def test_read_entry_empty_stdin_keeps_generic_message():
    with pytest.raises(ValueError, match="requires a JSON record via --body or stdin"):
        capture.read_entry(stdin_text="")


def test_read_entry_valid_body_file_returns_dict(tmp_path):
    good = tmp_path / "ok.json"
    good.write_text(json.dumps({"title": "hi"}), encoding="utf-8")
    assert capture.read_entry(str(good)) == {"title": "hi"}


def test_log_coerces_malformed_ts_losslessly(qiju_env):
    # Qiju is lossless: a bad ts must not fail the log; it is coerced to a parseable value.
    entry_id = capture.log_entry(
        sample_entry(ts="not-a-date"),
        source="manual",
        project="repo",
        cwd=qiju_env["project"],
    )
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    written = util.read_jsonl(qiju_paths.long_jsonl)
    assert len(written) == 1
    assert util.try_parse_iso(written[0]["ts"]) is not None
