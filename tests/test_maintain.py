from __future__ import annotations

from datetime import datetime

from qiju import archive, capture, maintain, paths, util
from tests.conftest import sample_entry


def test_short_rotation_keeps_long(qiju_env):
    old = sample_entry(ts="2026-01-01T10:00:00+10:00")
    capture.log_entry(old, source="manual", project="repo", cwd=qiju_env["project"])
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    result = maintain.maintain(project="repo", cwd=qiju_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    assert result["rotation"]["removed"] == 1
    assert util.read_jsonl(qiju_paths.short_jsonl) == []
    assert len(util.read_jsonl(qiju_paths.long_jsonl)) == 1


def test_small_old_partition_stays_in_jsonl(qiju_env):
    capture.log_entry(sample_entry(ts="2026-01-01T10:00:00+10:00"), source="manual", project="repo", cwd=qiju_env["project"])
    maintain.maintain(project="repo", cwd=qiju_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    assert util.read_jsonl(qiju_paths.long_jsonl)
    assert not qiju_paths.archive_partition("2026-01").exists()


def test_max_age_archives_small_partition(qiju_env, monkeypatch):
    monkeypatch.setattr(maintain, "MAX_SMALL_PARTITION_AGE_DAYS", 30)
    capture.log_entry(sample_entry(ts="2026-01-01T10:00:00+10:00"), source="manual", project="repo", cwd=qiju_env["project"])
    maintain.maintain(project="repo", cwd=qiju_env["project"], now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"))
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    archived = archive.read_parquet(qiju_paths.archive_partition("2026-01"))
    assert len(archived) == 1
    assert util.read_jsonl(qiju_paths.long_jsonl) == []



def test_maintain_tolerates_preexisting_malformed_ts(qiju_env):
    # Simulate pre-existing/hand-edited bad data written directly to the long tier.
    home = qiju_env["home"]
    long_file = home / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    util.append_jsonl(long_file, sample_entry(id="bad:1", ts="not-a-date"))
    util.append_jsonl(long_file, sample_entry(id="good:1", ts="2026-01-01T10:00:00+10:00"))

    # Must not raise on the malformed entry.
    maintain.maintain(
        project="repo",
        cwd=qiju_env["project"],
        now=datetime.fromisoformat("2026-05-31T10:00:00+10:00"),
    )

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    remaining = {entry["id"] for entry in util.read_jsonl(qiju_paths.long_jsonl)}
    # The malformed entry is never archived; the good one is processed normally.
    assert "bad:1" in remaining
    assert not qiju_paths.archive_partition("not-a-").exists()


def test_maintain_sweeps_stale_staging_file(qiju_env):
    import os
    from datetime import timedelta

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    paths.ensure_base_dirs(qiju_paths)
    now = datetime.now().astimezone()
    stale = qiju_paths.tmp_dir / "qiju-entry.claude.stale.json"
    fresh = qiju_paths.tmp_dir / "qiju-entry.claude.fresh.json"
    stale.write_text("{}")
    fresh.write_text("{}")
    old = (now - timedelta(hours=48)).timestamp()
    os.utime(stale, (old, old))

    result = maintain.maintain(project="repo", cwd=qiju_env["project"], now=now)
    assert result["staging_sweep"]["removed"] == 1
    assert result["staging_sweep"]["kept"] == 1
    assert not stale.exists()
    assert fresh.exists()


def test_maintain_sweep_dry_run_removes_nothing(qiju_env):
    import os
    from datetime import timedelta

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    paths.ensure_base_dirs(qiju_paths)
    now = datetime.now().astimezone()
    stale = qiju_paths.tmp_dir / "qiju-entry.claude.stale.json"
    stale.write_text("{}")
    old = (now - timedelta(hours=48)).timestamp()
    os.utime(stale, (old, old))

    result = maintain.maintain(project="repo", cwd=qiju_env["project"], now=now, dry_run=True)
    assert result["staging_sweep"]["removed"] == 1
    assert stale.exists()  # dry-run reported but did not delete


def test_maintain_sweep_never_touches_symlink_or_non_managed(qiju_env):
    import os
    from datetime import timedelta

    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    paths.ensure_base_dirs(qiju_paths)
    now = datetime.now().astimezone()
    old = (now - timedelta(hours=48)).timestamp()

    # (a) a genuine stale staging file -> swept
    genuine = qiju_paths.tmp_dir / "qiju-entry.claude.genuine.json"
    genuine.write_text("{}")
    os.utime(genuine, (old, old))

    # (b) an aged SYMLINK whose name matches the glob -> must be skipped (islink guard)
    secret = qiju_paths.project_root / "secret.txt"
    secret.write_text("do not delete")
    link = qiju_paths.tmp_dir / "qiju-entry.claude.link.json"
    link.symlink_to(secret)
    os.utime(link, (old, old), follow_symlinks=False)

    # (c) an aged file whose name does NOT match the staging glob -> must be skipped
    non_managed = qiju_paths.tmp_dir / "keep-me.json"
    non_managed.write_text("{}")
    os.utime(non_managed, (old, old))

    result = maintain.maintain(project="repo", cwd=qiju_env["project"], now=now)
    assert result["staging_sweep"]["removed"] == 1
    assert not genuine.exists()
    assert link.exists() and secret.exists()  # symlink + its target untouched
    assert non_managed.exists()               # non-managed name untouched
