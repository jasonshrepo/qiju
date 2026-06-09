from __future__ import annotations

from datetime import datetime

from scripts import archive, capture, maintain, paths, util
from tests.conftest import sample_entry


def test_short_rotation_keeps_long(kedu_env):
    old = sample_entry(ts="2026-01-01T10:00:00+10:00")
    capture.log_entry(old, source="manual", project="repo", cwd=kedu_env["project"])
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    result = maintain.maintain(project="repo", cwd=kedu_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    assert result["rotation"]["removed"] == 1
    assert util.read_jsonl(kedu_paths.short_jsonl) == []
    assert len(util.read_jsonl(kedu_paths.long_jsonl)) == 1


def test_small_old_partition_stays_in_jsonl(kedu_env):
    capture.log_entry(sample_entry(ts="2026-01-01T10:00:00+10:00"), source="manual", project="repo", cwd=kedu_env["project"])
    maintain.maintain(project="repo", cwd=kedu_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    assert util.read_jsonl(kedu_paths.long_jsonl)
    assert not kedu_paths.archive_partition("2026-01").exists()


def test_max_age_archives_small_partition(kedu_env, monkeypatch):
    monkeypatch.setattr(maintain, "MAX_SMALL_PARTITION_AGE_DAYS", 30)
    capture.log_entry(sample_entry(ts="2026-01-01T10:00:00+10:00"), source="manual", project="repo", cwd=kedu_env["project"])
    maintain.maintain(project="repo", cwd=kedu_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    archived = archive.read_parquet(kedu_paths.archive_partition("2026-01"))
    assert len(archived) == 1
    assert util.read_jsonl(kedu_paths.long_jsonl) == []



def test_maintain_tolerates_preexisting_malformed_ts(kedu_env):
    # Simulate pre-existing/hand-edited bad data written directly to the long tier.
    home = kedu_env["home"]
    long_file = home / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    util.append_jsonl(long_file, sample_entry(id="bad:1", ts="not-a-date"))
    util.append_jsonl(long_file, sample_entry(id="good:1", ts="2026-01-01T10:00:00+10:00"))

    # Must not raise on the malformed entry.
    maintain.maintain(
        project="repo",
        cwd=kedu_env["project"],
        now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"),
    )

    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    remaining = {entry["id"] for entry in util.read_jsonl(kedu_paths.long_jsonl)}
    # The malformed entry is never archived; the good one is processed normally.
    assert "bad:1" in remaining
    assert not kedu_paths.archive_partition("not-a-").exists()
