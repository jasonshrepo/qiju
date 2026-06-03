from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from scripts import capture, paths
from tests.conftest import sample_entry


def test_state_rebuilt_after_log(kedu_env):
    capture.log_entry(sample_entry(next_steps=["ship v1"]), source="manual", project="repo", cwd=kedu_env["project"])
    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    content = kedu_paths.state_md.read_text(encoding="utf-8")
    assert "# Kedu State" in content
    assert "ship v1" in content
    assert "Security fixes" in content
    assert "claude-code" in content


def test_state_file_is_complete_after_concurrent_logs(kedu_env):
    barrier = Barrier(2)

    def write_entry(index: int) -> str:
        barrier.wait(timeout=5)
        entry = sample_entry(
            title=f"Concurrent state write {index}",
            body_md=f"Body {index}",
            next_steps=[f"state step {index}"],
        )
        entry.pop("id")
        return capture.log_entry(
            entry,
            source="manual",
            project="repo",
            cwd=kedu_env["project"],
            session_id=f"state-session-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(write_entry, [1, 2]))

    assert sorted(ids) == ["state-session-1:1", "state-session-2:1"]

    kedu_paths = paths.resolve_paths(project="repo", cwd=kedu_env["project"])
    content = kedu_paths.state_md.read_text(encoding="utf-8")
    assert content
    assert content.endswith("\n")
    assert content.startswith("# Kedu State")
    assert "Generated:" in content
    assert "## Open Items" in content
    assert "## Active Decisions" in content
    assert "## Entry Index" in content
    assert "| Date | Title | Agent | Source | ID |" in content
    assert "|------|-------|-------|--------|----|" in content
