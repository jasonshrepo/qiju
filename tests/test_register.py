from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from qiju import register


def _concurrent_register_worker(args: tuple[str, str, str]) -> str | None:
    """Top-level (picklable) worker: register one project in a child process.

    Returns None on success, or a "Type: message" string on failure so the
    parent can assert there were zero process failures.
    """
    qiju_home_str, path_str, slug = args
    os.environ["QIJU_HOME"] = qiju_home_str
    from qiju import register as register_mod

    try:
        register_mod.register_project(path_str, slug)
        return None
    except Exception as exc:  # noqa: BLE001 - report any failure back to the parent
        return f"{type(exc).__name__}: {exc}"


def test_register_project_round_trip(qiju_env, tmp_path):
    project = tmp_path / "myproject"
    project.mkdir()
    (project / ".qiju").mkdir()
    (project / ".qiju" / "config.json").write_text('{"project": "myproject"}', encoding="utf-8")

    register.register_project(project, "myproject")
    projects = register.read_registry()
    assert str(project.resolve()) in projects
    assert projects[str(project.resolve())] == "myproject"


def test_register_project_slug_update_is_idempotent(qiju_env, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".qiju").mkdir()
    (project / ".qiju" / "config.json").write_text('{"project": "proj"}', encoding="utf-8")

    register.register_project(project, "proj")
    register.register_project(project, "proj-renamed")
    projects = register.read_registry()
    assert projects[str(project.resolve())] == "proj-renamed"
    # Only one entry
    assert sum(1 for k in projects if k == str(project.resolve())) == 1


def test_read_registry_returns_empty_when_missing(qiju_env):
    reg_path = register.register_path()
    assert not reg_path.exists()
    assert register.read_registry() == {}


def test_read_registry_returns_empty_on_corrupt_file(qiju_env):
    reg_path = register.register_path()
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text("not valid json{{{{", encoding="utf-8")
    assert register.read_registry() == {}


def test_atomic_write_leaves_no_tmp_file(qiju_env, tmp_path):
    project = tmp_path / "atomictest"
    project.mkdir()
    register.register_project(project, "atomictest")
    tmp = register.register_path().parent / (register.register_path().name + ".tmp")
    assert not tmp.exists()
    assert register.register_path().exists()


def test_registered_roots_prunes_missing_config(qiju_env, tmp_path):
    existing = tmp_path / "alive"
    existing.mkdir()
    (existing / ".qiju").mkdir()
    (existing / ".qiju" / "config.json").write_text('{"project":"alive"}', encoding="utf-8")

    gone = tmp_path / "gone"
    gone.mkdir()
    register.register_project(existing, "alive")
    register.register_project(gone, "gone")

    live, pruned = register.registered_roots()
    live_strs = [str(p.resolve()) for p in live]
    assert str(existing.resolve()) in live_strs
    assert str(gone.resolve()) not in live_strs
    assert str(gone.resolve()) in pruned

    # Registry was rewritten without the stale entry
    projects = register.read_registry()
    assert str(gone.resolve()) not in projects
    assert str(existing.resolve()) in projects


def test_registered_roots_prune_false_does_not_write(qiju_env, tmp_path):
    gone = tmp_path / "gone"
    gone.mkdir()
    register.register_project(gone, "gone")
    gone.rmdir()

    live, pruned = register.registered_roots(prune=False)

    assert str(gone.resolve()) in pruned
    assert not any(str(p) == str(gone.resolve()) for p in live)
    # Stale entry must still be in the on-disk registry
    projects = register.read_registry()
    assert str(gone.resolve()) in projects


def test_registered_roots_empty_when_no_registry(qiju_env):
    live, pruned = register.registered_roots()
    assert live == []
    assert pruned == []


def test_unregister_project_removes_only_named_path(qiju_env, tmp_path):
    p1 = tmp_path / "p1"
    p2 = tmp_path / "p2"
    p1.mkdir()
    p2.mkdir()
    register.register_project(p1, "p1")
    register.register_project(p2, "p2")

    removed = register.unregister_project(p1)
    assert removed is True
    projects = register.read_registry()
    assert str(p1.resolve()) not in projects
    assert str(p2.resolve()) in projects


def test_unregister_project_returns_false_when_not_registered(qiju_env, tmp_path):
    p = tmp_path / "nothere"
    assert register.unregister_project(p) is False


# --- concurrency (release gate) ---

def test_concurrent_register_no_loss(qiju_env, tmp_path):
    """30 concurrent registrations of distinct projects: no process failures,
    no lost entries, no leftover temp files. Reproduces the Codex gate."""
    qiju_home_str = os.environ["QIJU_HOME"]
    n = 30
    jobs: list[tuple[str, str, str]] = []
    for i in range(n):
        proj = tmp_path / f"proj{i}"
        proj.mkdir()
        jobs.append((qiju_home_str, str(proj), f"slug{i}"))

    with ProcessPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(_concurrent_register_worker, jobs))

    failures = [r for r in results if r is not None]
    assert failures == [], f"workers failed: {failures}"

    projects = register.read_registry()
    assert len(projects) == n
    for i in range(n):
        key = str((tmp_path / f"proj{i}").resolve())
        assert projects.get(key) == f"slug{i}"

    leftovers = [p.name for p in register.registry_dir().iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_concurrent_register_same_path(qiju_env, tmp_path):
    """30 concurrent registrations of the SAME project: idempotent, exactly one
    entry, no failures, no leftover temp files."""
    qiju_home_str = os.environ["QIJU_HOME"]
    proj = tmp_path / "shared"
    proj.mkdir()
    n = 30
    jobs = [(qiju_home_str, str(proj), f"slug{i}") for i in range(n)]

    with ProcessPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(_concurrent_register_worker, jobs))

    assert [r for r in results if r is not None] == []

    projects = register.read_registry()
    assert len(projects) == 1
    assert str(proj.resolve()) in projects

    leftovers = [p.name for p in register.registry_dir().iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


# --- legacy migration ---

def test_migrates_legacy_single_file(qiju_env, tmp_path):
    home = Path(os.environ["QIJU_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    legacy = home / "project-register.json"
    p1 = str((tmp_path / "a").resolve())
    p2 = str((tmp_path / "b").resolve())
    legacy.write_text(
        json.dumps({"schema_version": 1, "projects": {p1: "a", p2: "b"}}),
        encoding="utf-8",
    )

    projects = register.read_registry()
    assert projects == {p1: "a", p2: "b"}

    json_files = [p for p in register.registry_dir().iterdir() if p.suffix == ".json"]
    assert len(json_files) == 2
    assert not legacy.exists()
    assert (home / "project-register.json.migrated").exists()

    # Idempotent: a second access does not re-import or duplicate.
    assert register.read_registry() == {p1: "a", p2: "b"}
    json_files_again = [p for p in register.registry_dir().iterdir() if p.suffix == ".json"]
    assert len(json_files_again) == 2


def test_registered_roots_prune_false_keeps_entry_file(qiju_env, tmp_path):
    gone = tmp_path / "gone"
    gone.mkdir()
    register.register_project(gone, "gone")
    entry_file = register._entry_path(str(gone.resolve()))
    assert entry_file.exists()
    gone.rmdir()

    register.registered_roots(prune=False)
    assert entry_file.exists()  # prune=False must not unlink the entry file

    register.registered_roots(prune=True)
    assert not entry_file.exists()  # prune=True removes only this entry's file
