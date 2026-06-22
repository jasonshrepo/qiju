from __future__ import annotations

from qiju import capture, search, util
from tests.conftest import sample_entry


def test_current_project_scope(qiju_env):
    capture.log_entry(sample_entry(id="a:1", project="repo"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="b:1", project="other", body_md="auth in other"), source="manual", project="other", cwd=qiju_env["project"])
    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], query="auth")
    assert [entry["project"] for entry in results] == ["repo"]


def test_all_scope_searches_multiple_projects(qiju_env):
    capture.log_entry(sample_entry(id="a:1", body_md="deploy auth"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="b:1", body_md="deploy auth"), source="manual", project="other", cwd=qiju_env["project"])
    results = search.search_entries(scope="all", cwd=qiju_env["project"], query="deploy")
    assert {entry["project"] for entry in results} == {"repo", "other"}


def test_sort_order_controls_direction(qiju_env):
    capture.log_entry(sample_entry(id="a:1", ts="2026-06-01T10:00:00+10:00"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="b:1", ts="2026-06-03T10:00:00+10:00"), source="manual", project="repo", cwd=qiju_env["project"])
    desc = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"])
    assert [entry["id"] for entry in desc] == ["b:1", "a:1"]
    asc = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], order="asc")
    assert [entry["id"] for entry in asc] == ["a:1", "b:1"]


def test_sort_by_arbitrary_field(qiju_env):
    capture.log_entry(sample_entry(id="a:1", title="Zeta"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="b:1", title="Alpha"), source="manual", project="repo", cwd=qiju_env["project"])
    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], sort="title", order="asc")
    assert [entry["title"] for entry in results] == ["Alpha", "Zeta"]


def test_body_scan_finds_terms_not_in_metadata(qiju_env):
    entry = sample_entry(search_terms=[], title="Unrelated", tags=[], next_steps=[], body_md="Need to fix auth_cookie_expired")
    capture.log_entry(entry, source="manual", project="repo", cwd=qiju_env["project"])
    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], query="auth_cookie_expired")
    assert len(results) == 1


def test_agent_filter(qiju_env):
    capture.log_entry(sample_entry(id="claude:1", agent="claude-code", body_md="shared fix"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="codex:1", agent="codex", body_md="shared fix"), source="manual", project="repo", cwd=qiju_env["project"])
    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], query="shared", agent="codex")
    assert [entry["agent"] for entry in results] == ["codex"]


def test_session_filter_returns_single_session_record(qiju_env):
    capture.log_entry(sample_entry(id="abc:1", title="Target"), source="manual", project="repo", cwd=qiju_env["project"])
    capture.log_entry(sample_entry(id="other:1", title="Other"), source="manual", project="repo", cwd=qiju_env["project"])

    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], session="abc")

    assert [entry["id"] for entry in results] == ["abc:1"]


def test_session_filter_returns_multi_record_session_in_sequence_order(qiju_env):
    capture.log_entry(
        sample_entry(id="abc:2", ts="2026-06-03T10:00:00+10:00", title="Second"),
        source="manual", project="repo", cwd=qiju_env["project"],
    )
    capture.log_entry(
        sample_entry(id="abc:1", ts="2026-06-04T10:00:00+10:00", title="First"),
        source="manual", project="repo", cwd=qiju_env["project"],
    )
    capture.log_entry(
        sample_entry(id="other:1", ts="2026-06-01T10:00:00+10:00", title="Other"),
        source="manual", project="repo", cwd=qiju_env["project"],
    )

    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], session="abc")

    assert [entry["id"] for entry in results] == ["abc:1", "abc:2"]


def test_session_filter_returns_empty_for_missing_session(qiju_env):
    capture.log_entry(sample_entry(id="abc:1"), source="manual", project="repo", cwd=qiju_env["project"])

    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"], session="missing")

    assert results == []


def test_rollup_next_steps_dedupes_keeping_newest(qiju_env):
    capture.log_entry(
        sample_entry(id="old:1", ts="2026-06-01T10:00:00+10:00", next_steps=["Ship release", "Write docs"]),
        source="manual", project="repo", cwd=qiju_env["project"],
    )
    capture.log_entry(
        sample_entry(id="new:1", ts="2026-06-05T10:00:00+10:00", next_steps=["ship release", "Add tests"]),
        source="manual", project="repo", cwd=qiju_env["project"],
    )
    results = search.search_entries(scope="current_project", project="repo", cwd=qiju_env["project"])
    rolled = search.rollup_next_steps(results)
    texts = [text for text, _ in rolled]
    # "Ship release"/"ship release" dedupe to one entry, keeping the newest occurrence.
    assert texts.count("ship release") == 1
    assert "Ship release" not in texts
    assert "Add tests" in texts
    assert "Write docs" in texts
    # The kept duplicate is paired with the newest source record.
    ship_source = next(src for text, src in rolled if text == "ship release")
    assert ship_source["id"] == "new:1"


def test_rollup_next_steps_respects_time_filter(qiju_env):
    home = qiju_env["home"]
    long_file = home / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    util.append_jsonl(long_file, sample_entry(id="inrange:1", ts="2026-06-02T10:00:00+10:00", next_steps=["In-range task"]))
    util.append_jsonl(long_file, sample_entry(id="outrange:1", ts="2026-01-01T10:00:00+10:00", next_steps=["Out-of-range task"]))

    results = search.search_entries(
        scope="current_project", project="repo", cwd=qiju_env["project"],
        since="2026-06-01", until="2026-06-03",
    )
    rolled = search.rollup_next_steps(results)
    texts = [text for text, _ in rolled]
    assert "In-range task" in texts
    assert "Out-of-range task" not in texts


def test_format_actions_cli_output(qiju_env, capsys):
    from qiju import cli as qiju_mod

    capture.log_entry(
        sample_entry(id="a:1", ts="2026-06-05T10:00:00+10:00", title="Auth work", next_steps=["Finish login"]),
        source="manual", project="repo", cwd=qiju_env["project"],
    )
    args = qiju_mod.build_parser().parse_args([
        "search", "--scope", "current_project", "--project", "repo", "--format", "actions",
    ])
    rc = qiju_mod.cmd_search(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert '- [ ] Finish login  (from: 2026-06-05 "Auth work")' in out


def test_time_filtered_search_excludes_malformed_ts(qiju_env):
    home = qiju_env["home"]
    long_file = home / "long" / "repo.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    util.append_jsonl(long_file, sample_entry(id="bad:1", ts="not-a-date"))
    util.append_jsonl(long_file, sample_entry(id="good:1", ts="2026-06-02T10:00:00+10:00"))

    results = search.search_entries(
        scope="current_project",
        project="repo",
        cwd=qiju_env["project"],
        since="2026-06-01",
        until="2026-06-03",
    )
    ids = {entry["id"] for entry in results}
    assert "good:1" in ids
    assert "bad:1" not in ids


# ---------------------------------------------------------------------------
# Case-normalization tests
# ---------------------------------------------------------------------------

def test_slugify_project_lowercases():
    from qiju.paths import slugify_project
    assert slugify_project("MyProject") == "myproject"
    assert slugify_project("MyProject") == "myproject"


def test_slugify_project_separator_and_strip_unchanged():
    from qiju.paths import slugify_project
    # Separator collapsing still works after lowercasing.
    assert slugify_project("My  Project!!") == "my-project"
    # Leading/trailing separators stripped.
    assert slugify_project("--hello--") == "hello"
    # Dots, underscores, hyphens preserved.
    assert slugify_project("my.proj_v2") == "my.proj_v2"


def test_log_with_uppercase_project_stored_as_lowercase(qiju_env, monkeypatch):
    """Entries logged with a mixed-case project name are stored lowercase."""
    monkeypatch.setenv("QIJU_HOME", str(qiju_env["home"]))
    capture.log_entry(
        sample_entry(id="upper:1", project="MyProject"),
        source="manual",
        project="MyProject",
        cwd=qiju_env["project"],
    )
    # The long file must use the lowercase slug.
    long_file = qiju_env["home"] / "long" / "myproject.jsonl"
    assert long_file.exists(), "long file should be lowercase"

    entries = util.read_jsonl(long_file)
    assert len(entries) == 1
    assert entries[0]["project"] == "myproject"


def test_search_finds_entry_logged_with_uppercase_project(qiju_env, monkeypatch):
    """search_entries with lowercase project finds entries originally logged uppercase."""
    monkeypatch.setenv("QIJU_HOME", str(qiju_env["home"]))
    capture.log_entry(
        sample_entry(id="upper:2", project="MyProject", title="Case test"),
        source="manual",
        project="MyProject",
        cwd=qiju_env["project"],
    )
    results = search.search_entries(
        scope="current_project",
        project="myproject",
        cwd=qiju_env["project"],
    )
    assert any(e["id"] == "upper:2" for e in results)


def test_search_case_insensitive_legacy_entry(qiju_env, monkeypatch):
    """search_entries finds a legacy entry whose project field is mixed-case."""
    monkeypatch.setenv("QIJU_HOME", str(qiju_env["home"]))
    home = qiju_env["home"]
    long_file = home / "long" / "myproject.jsonl"
    long_file.parent.mkdir(parents=True, exist_ok=True)
    # Write a legacy entry directly with mixed-case project field.
    util.append_jsonl(long_file, sample_entry(id="legacy:1", project="MyProject", title="Legacy"))

    results = search.search_entries(
        scope="current_project",
        project="myproject",
        cwd=qiju_env["project"],
    )
    assert any(e["id"] == "legacy:1" for e in results)
