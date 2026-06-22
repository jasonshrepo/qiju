from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts import paths, staging


def _tmp_dir(qiju_env) -> Path:
    p = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    return p.tmp_dir


def test_allocate_returns_unique_empty_file(qiju_env):
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="codex-desktop")
    assert path.exists()
    assert path.read_text() == ""
    assert path.parent == _tmp_dir(qiju_env)
    assert path.name.startswith("qiju-entry.codex-desktop.")
    assert path.name.endswith(".json")


def test_allocate_two_calls_differ(qiju_env):
    a = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="codex-desktop")
    b = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="codex-desktop")
    assert a != b


def test_allocate_label_falls_back_to_env(qiju_env, monkeypatch):
    monkeypatch.setenv("QIJU_AGENT", "kiro-ide")
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"])
    assert path.name.startswith("qiju-entry.kiro-ide.")


def test_allocate_label_defaults_to_agent_when_blank(qiju_env, monkeypatch):
    monkeypatch.delenv("QIJU_AGENT", raising=False)
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"])
    assert path.name.startswith("qiju-entry.agent.")


def test_allocate_retries_on_collision(qiju_env, monkeypatch):
    # Force the first UUID to collide with an existing file, then succeed with the next.
    seq = iter(["dead", "beef"])

    class _U:
        def __init__(self, hex):
            self.hex = hex

    monkeypatch.setattr(staging.uuid, "uuid4", lambda: _U(next(seq)))
    tmp = _tmp_dir(qiju_env)
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "qiju-entry.agent.dead.json").write_text("collision")
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"])
    assert path.name == "qiju-entry.agent.beef.json"


def test_guard_accepts_genuine_staged_file(qiju_env):
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="claude")
    ok, reason, rp = staging.is_managed_staging_file(path, _tmp_dir(qiju_env))
    assert ok and reason is None
    assert rp == Path(os.path.realpath(path))


def test_guard_refuses_symlink(qiju_env, tmp_path):
    tmp = _tmp_dir(qiju_env)
    tmp.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "secret"
    target.write_text("secret")
    link = tmp / "qiju-entry.agent.link.json"
    link.symlink_to(target)
    ok, reason, rp = staging.is_managed_staging_file(link, tmp)
    assert not ok and rp is None
    assert "symlink" in reason


def test_guard_refuses_path_outside_tmp(qiju_env, tmp_path):
    outside = tmp_path / "qiju-entry.agent.x.json"
    outside.write_text("{}")
    ok, reason, rp = staging.is_managed_staging_file(outside, _tmp_dir(qiju_env))
    assert not ok and rp is None


def test_guard_refuses_traversal(qiju_env, tmp_path):
    tmp = _tmp_dir(qiju_env)
    tmp.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "qiju-entry.agent.evil.json"
    outside.write_text("{}")
    traversal = tmp / ".." / "qiju-entry.agent.evil.json"
    # realpath of the traversal lands outside tmp_dir -> refused.
    ok, reason, rp = staging.is_managed_staging_file(traversal, tmp)
    assert not ok and rp is None


def test_guard_refuses_wrong_name(qiju_env):
    tmp = _tmp_dir(qiju_env)
    tmp.mkdir(parents=True, exist_ok=True)
    other = tmp / "not-staging.json"
    other.write_text("{}")
    ok, reason, rp = staging.is_managed_staging_file(other, tmp)
    assert not ok and rp is None
    assert "name does not match" in reason


def test_safe_cleanup_deletes_managed_file(qiju_env):
    path = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="claude")
    deleted, reason = staging.safe_cleanup(path, project="repo", cwd=qiju_env["project"])
    assert deleted and reason is None
    assert not path.exists()


def test_safe_cleanup_refuses_non_managed(qiju_env, tmp_path):
    other = tmp_path / "record.json"
    other.write_text("{}")
    deleted, reason = staging.safe_cleanup(other, project="repo", cwd=qiju_env["project"])
    assert not deleted
    assert other.exists()


def test_safe_cleanup_no_body(qiju_env):
    deleted, reason = staging.safe_cleanup(None, project="repo", cwd=qiju_env["project"])
    assert not deleted
    assert "no --body" in reason


def test_concurrent_same_label_writers_no_loss(qiju_env):
    # Two same-agent-label writers each allocate + write + log concurrently. Proves the
    # UUID + exclusive-create (not the label) gives each its own private staging file, so
    # neither overwrites the other -> two distinct durable records, no loss.
    import json
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from scripts import capture, util

    barrier = Barrier(2)

    def worker(n):
        path = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent="codex-desktop")
        path.write_text(
            json.dumps({"title": f"t{n}", "body_md": f"b{n}", "tags": [], "search_terms": [], "next_steps": []}),
            encoding="utf-8",
        )
        barrier.wait()  # maximize overlap
        raw = capture.read_entry(str(path))
        return capture.log_entry(
            raw, source="manual", project="repo", cwd=qiju_env["project"], session_id=f"sess-{n}"
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        ids = list(ex.map(worker, [1, 2]))

    assert len(set(ids)) == 2
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    records = util.read_jsonl(qiju_paths.long_jsonl)
    assert len(records) == 2
    # No loss: BOTH distinct payloads survived, not merely two rows of either content.
    assert {r["title"] for r in records} == {"t1", "t2"}
    assert {r["body_md"] for r in records} == {"b1", "b2"}


def test_concurrent_cross_agent_writers_no_loss(qiju_env):
    import json
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from scripts import capture, util

    barrier = Barrier(2)

    def worker(item):
        n, agent = item
        path = staging.allocate_staging(project="repo", cwd=qiju_env["project"], agent=agent)
        path.write_text(
            json.dumps({"title": f"t{n}", "body_md": f"b{n}", "tags": [], "search_terms": [], "next_steps": []}),
            encoding="utf-8",
        )
        barrier.wait()
        raw = capture.read_entry(str(path))
        return capture.log_entry(
            raw, source="manual", project="repo", agent=agent, cwd=qiju_env["project"], session_id=f"sess-{n}"
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        ids = list(ex.map(worker, [(1, "claude"), (2, "codex")]))

    assert len(set(ids)) == 2
    qiju_paths = paths.resolve_paths(project="repo", cwd=qiju_env["project"])
    records = util.read_jsonl(qiju_paths.long_jsonl)
    assert len(records) == 2
    # No loss: BOTH distinct payloads survived, not merely two rows of either content.
    assert {r["title"] for r in records} == {"t1", "t2"}
    assert {r["body_md"] for r in records} == {"b1", "b2"}
