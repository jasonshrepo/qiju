from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

from scripts import archive, capture, maintain, paths, util
from tests.conftest import sample_entry


def test_log_writes_short_and_long(kedu_env):
    entry_id = capture.log_entry(sample_entry(), source="manual", project="repo", cwd=kedu_env["project"])
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    assert entry_id == "session-1:1"
    assert len(util.read_jsonl(kedu_paths.short_jsonl)) == 1
    assert len(util.read_jsonl(kedu_paths.long_jsonl)) == 1


def test_log_is_idempotent(kedu_env):
    entry = sample_entry()
    capture.log_entry(entry, source="manual", project="repo", cwd=kedu_env["project"])
    capture.log_entry(entry, source="manual", project="repo", cwd=kedu_env["project"])
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    assert len(util.read_jsonl(kedu_paths.short_jsonl)) == 1
    assert len(util.read_jsonl(kedu_paths.long_jsonl)) == 1


def test_capture_redacts_before_write(kedu_env):
    capture.log_entry(
        sample_entry(body_md="AKIAIOSFODNN7EXAMPLE"),
        source="manual",
        project="repo",
        cwd=kedu_env["project"],
    )
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    written = util.read_jsonl(kedu_paths.long_jsonl)[0]
    assert written["body_md"] == "[REDACTED:aws_access_key]"
    assert written["redactions"]


def test_capture_accepts_agent_identity(kedu_env):
    capture.log_entry(
        sample_entry(id="agent-test:1", agent="ignored"),
        source="manual",
        agent="codex",
        project="repo",
        cwd=kedu_env["project"],
    )
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    written = util.read_jsonl(kedu_paths.long_jsonl)[0]
    assert written["agent"] == "codex"


def test_agents_share_same_kedu_store(kedu_env):
    capture.log_entry(
        sample_entry(id="claude:1", agent="claude-code"),
        source="manual",
        agent="claude-code",
        project="repo",
        cwd=kedu_env["project"],
    )
    capture.log_entry(
        sample_entry(id="kiro:1", agent="kiro", title="Kiro review"),
        source="manual",
        agent="kiro",
        project="repo",
        cwd=kedu_env["project"],
    )
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    entries = util.read_jsonl(kedu_paths.long_jsonl)
    assert kedu_paths.long_jsonl == kedu_env["home"] / "long" / "repo.jsonl"
    assert {entry["agent"] for entry in entries} == {"claude-code", "kiro"}
    assert not (kedu_env["home"] / "claude-code").exists()
    assert not (kedu_env["home"] / "kiro").exists()


def test_log_continues_sequence_when_session_records_are_archived(kedu_env, monkeypatch):
    monkeypatch.setattr(maintain, "MAX_SMALL_PARTITION_AGE_DAYS", 30)
    old_entry = sample_entry(ts="2026-01-01T10:00:00+10:00")
    old_entry.pop("id")

    first_id = capture.log_entry(
        old_entry,
        source="manual",
        project="repo",
        cwd=kedu_env["project"],
        session_id="archive-session",
    )
    assert first_id == "archive-session:1"

    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    maintain.maintain(
        project="repo",
        cwd=kedu_env["project"],
        now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"),
    )
    assert util.read_jsonl(kedu_paths.short_jsonl) == []
    assert util.read_jsonl(kedu_paths.long_jsonl) == []
    assert {entry["id"] for entry in archive.read_parquet(kedu_paths.archive_partition("2026-01"))} == {first_id}

    new_entry = sample_entry(title="Follow-up after archive", ts="2026-06-01T10:00:00+10:00")
    new_entry.pop("id")
    second_id = capture.log_entry(
        new_entry,
        source="manual",
        project="repo",
        cwd=kedu_env["project"],
        session_id="archive-session",
    )

    assert second_id == "archive-session:2"
    assert [entry["id"] for entry in util.read_jsonl(kedu_paths.long_jsonl)] == [second_id]


def test_concurrent_same_session_logs_get_distinct_generated_ids(kedu_env, monkeypatch):
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
            cwd=kedu_env["project"],
            session_id="thread-session",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(write_entry, [1, 2]))

    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    long_entries = util.read_jsonl(kedu_paths.long_jsonl)

    assert sorted(ids) == ["thread-session:1", "thread-session:2"]
    assert sorted(entry["id"] for entry in long_entries) == ["thread-session:1", "thread-session:2"]
