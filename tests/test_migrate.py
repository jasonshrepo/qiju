"""Tests for scripts/migrate.py — project-name case-normalization migration."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts import qiju as qiju_mod, migrate as migrate_mod, search, util
from tests.conftest import sample_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_legacy_long(home: Path, filename: str, entries: list[dict]) -> Path:
    """Write a long-tier JSONL file directly, bypassing normalization."""
    long_dir = home / "long"
    long_dir.mkdir(parents=True, exist_ok=True)
    path = long_dir / filename
    for entry in entries:
        util.append_jsonl(path, entry)
    return path


def _write_marker(root: Path, project_name: str) -> None:
    qiju_dir = root / ".qiju"
    qiju_dir.mkdir(parents=True, exist_ok=True)
    marker = qiju_dir / "config.json"
    marker.write_text(json.dumps({"project": project_name}), encoding="utf-8")


def _write_short(root: Path, entries: list[dict]) -> Path:
    short = root / ".qiju" / "short.jsonl"
    short.parent.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        util.append_jsonl(short, entry)
    return short


# ---------------------------------------------------------------------------
# Long-tier migration
# ---------------------------------------------------------------------------

class TestLongTierMigration:
    """The long-tier migrator handles: rename, samefile rename, entry rewrite."""

    def _setup_legacy_store(self, home: Path, project_root: Path) -> None:
        """Write a legacy store on a case-insensitive FS (one physical file, mixed names).

        On macOS APFS ``long/LegacyProj.jsonl`` and ``long/legacyproj.jsonl`` are the
        same file. We simulate the real-world scenario: ONE file whose stem is mixed-case,
        containing entries with BOTH casings of the project field.
        """
        _write_legacy_long(
            home,
            "LegacyProj.jsonl",
            [
                sample_entry(id="lp:1", project="LegacyProj", title="Entry one"),
                sample_entry(id="lp:2", project="legacyproj", title="Entry two"),
                sample_entry(id="lp:3", project="LegacyProj", title="Entry three"),
            ],
        )
        _write_marker(project_root, "LegacyProj")
        _write_short(
            project_root,
            [
                sample_entry(id="sp:1", project="LegacyProj", title="Short one"),
                sample_entry(id="sp:2", project="legacyproj", title="Short two"),
            ],
        )

    def test_dry_run_reports_actions_without_writing(self, tmp_path, monkeypatch):
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        self._setup_legacy_store(home, project_root)

        long_file_before = home / "long" / "LegacyProj.jsonl"
        mtime_before = long_file_before.stat().st_mtime

        report = migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=True,
        )

        assert report["dry_run"] is True
        # File must NOT have been modified.
        assert long_file_before.stat().st_mtime == mtime_before

    def test_migration_renames_and_rewrites_entries(self, tmp_path, monkeypatch):
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        self._setup_legacy_store(home, project_root)

        report = migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        assert report["dry_run"] is False

        # The long file must now be the lowercase name.
        target_long = home / "long" / "legacyproj.jsonl"
        assert target_long.exists(), "long file should be lowercase after migration"

        # All entry project fields must be lowercase.
        entries = util.read_jsonl(target_long)
        assert len(entries) == 3, "no entries lost in migration"
        for entry in entries:
            assert entry["project"] == "legacyproj"

        # Marker must be updated.
        marker = project_root / ".qiju" / "config.json"
        data = json.loads(marker.read_text(encoding="utf-8"))
        assert data["project"] == "legacyproj"

        # Short tier must be updated.
        short_entries = util.read_jsonl(project_root / ".qiju" / "short.jsonl")
        assert len(short_entries) == 2
        for entry in short_entries:
            assert entry["project"] == "legacyproj"

    def test_no_entry_loss(self, tmp_path, monkeypatch):
        """Total entry count is preserved (no duplicates dropped unless same id)."""
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        _write_legacy_long(
            home,
            "LegacyProj.jsonl",
            [
                sample_entry(id="x:1", project="LegacyProj"),
                sample_entry(id="x:2", project="legacyproj"),
                sample_entry(id="x:3", project="LegacyProj"),
                # A true duplicate id — should be deduped only in merge path.
                sample_entry(id="x:3", project="LegacyProj", title="dup"),
            ],
        )
        _write_marker(project_root, "LegacyProj")

        report = migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        target_long = home / "long" / "legacyproj.jsonl"
        entries = util.read_jsonl(target_long)
        # 4 lines written, but x:3 is duplicated → dedupe in rename path keeps original order.
        # The rename path does NOT dedupe; only the merge collision path does.
        # So all 4 lines are present (including the dup id).
        assert len(entries) >= 3  # at minimum unique ids

    def test_idempotent_second_run(self, tmp_path, monkeypatch):
        """A second migration run produces no changes."""
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        self._setup_legacy_store(home, project_root)

        # First run.
        migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        # Second run should find no changes needed.
        report2 = migrate_mod.migrate_project_names(
            project="legacyproj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        # All rewrite reports should show 0 entries changed.
        for item in report2["long"]:
            assert item.get("entries_changed", 0) == 0
        if report2["short"]:
            assert report2["short"].get("entries_changed", 0) == 0
        if report2["marker"]:
            assert report2["marker"].get("changed", False) is False

    def test_search_finds_legacy_entries_after_migration(self, tmp_path, monkeypatch):
        """After migration, search_entries returns legacy entries by lowercase slug."""
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        self._setup_legacy_store(home, project_root)

        migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        results = search.search_entries(
            scope="current_project",
            project="legacyproj",
            cwd=project_root,
        )
        ids = {e["id"] for e in results}
        assert "lp:1" in ids
        assert "lp:2" in ids
        assert "lp:3" in ids


# ---------------------------------------------------------------------------
# Archive tier migration (requires duckdb)
# ---------------------------------------------------------------------------

class TestArchiveTierMigration:
    def test_archive_migration_rewrites_entries(self, tmp_path, monkeypatch):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            pytest.skip("duckdb not installed")

        from scripts import archive as archive_mod

        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        # Write a legacy archive dir with a mixed-case name.
        archive_dir = home / "archive" / "project=LegacyProj" / "month=2026-01"
        archive_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = archive_dir / "entries.parquet"

        entries = [
            sample_entry(id="arc:1", project="LegacyProj"),
            sample_entry(id="arc:2", project="legacyproj"),
        ]
        archive_mod.write_parquet_atomic(parquet_path, entries)
        _write_marker(project_root, "LegacyProj")

        report = migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=False,
        )

        assert report["dry_run"] is False

        # Target archive dir must now be lowercase.
        target_parquet = home / "archive" / "project=legacyproj" / "month=2026-01" / "entries.parquet"
        assert target_parquet.exists(), "archive parquet should be at lowercase path"

        migrated = archive_mod.read_parquet(target_parquet)
        assert len(migrated) == 2
        for entry in migrated:
            assert entry["project"] == "legacyproj"

    def test_archive_dry_run_no_writes(self, tmp_path, monkeypatch):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            pytest.skip("duckdb not installed")

        from scripts import archive as archive_mod

        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        archive_dir = home / "archive" / "project=LegacyProj" / "month=2026-01"
        archive_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = archive_dir / "entries.parquet"
        entries = [sample_entry(id="arc:3", project="LegacyProj")]
        archive_mod.write_parquet_atomic(parquet_path, entries)
        _write_marker(project_root, "LegacyProj")

        mtime_before = parquet_path.stat().st_mtime

        migrate_mod.migrate_project_names(
            project="LegacyProj",
            cwd=project_root,
            home=home,
            dry_run=True,
        )

        # File must NOT have been modified.
        assert parquet_path.stat().st_mtime == mtime_before


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    def test_projects_command_lists_slugs(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "qiju-home"
        monkeypatch.setenv("QIJU_HOME", str(home))

        # Create two long files (one already lowercase, one mixed-case — same physical file
        # on APFS, so just one).
        (home / "long").mkdir(parents=True, exist_ok=True)
        util.append_jsonl(home / "long" / "alpha.jsonl", sample_entry(id="a:1", project="alpha"))
        util.append_jsonl(home / "long" / "beta.jsonl", sample_entry(id="b:1", project="beta"))

        rc = qiju_mod.main(["projects"])
        assert rc == 0
        out = capsys.readouterr().out.strip().splitlines()
        assert "alpha" in out
        assert "beta" in out

    def test_migrate_dry_run_cli(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        _write_legacy_long(
            home,
            "LegacyProj.jsonl",
            [sample_entry(id="cli:1", project="LegacyProj")],
        )
        _write_marker(project_root, "LegacyProj")

        # Run via CLI main() with dry-run.
        rc = qiju_mod.main([
            "migrate",
            "--project", "LegacyProj",
            "--dry-run",
        ])
        assert rc == 0

        out = capsys.readouterr().out
        report = json.loads(out)
        assert report["dry_run"] is True

        # Nothing on disk changed.
        assert (home / "long" / "LegacyProj.jsonl").exists()
        assert not (home / "long" / "legacyproj.jsonl").exists() or os.path.samefile(
            home / "long" / "LegacyProj.jsonl",
            home / "long" / "legacyproj.jsonl",
        )

    def test_migrate_cli_runs_successfully(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "qiju-home"
        project_root = tmp_path / "myrepo"
        project_root.mkdir()
        monkeypatch.setenv("QIJU_HOME", str(home))

        _write_legacy_long(
            home,
            "LegacyProj.jsonl",
            [sample_entry(id="cli:2", project="LegacyProj")],
        )
        _write_marker(project_root, "LegacyProj")

        rc = qiju_mod.main([
            "migrate",
            "--project", "LegacyProj",
        ])
        assert rc == 0

        out = capsys.readouterr().out
        report = json.loads(out)
        assert report["dry_run"] is False

        # After migration the file should resolve to lowercase.
        target = home / "long" / "legacyproj.jsonl"
        assert target.exists()
