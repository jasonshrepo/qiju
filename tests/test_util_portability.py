"""Cross-platform portability tests.

These exercise the platform-branched primitives added for Windows support. They run on
every OS, so each platform's branch of ``exclusive_lock``/``replace_atomic`` is validated
by that OS's own CI runner (POSIX ``fcntl`` here, Windows ``msvcrt`` on windows-latest).
"""
from __future__ import annotations

import threading
import time

import pytest

from qiju import util
from qiju.paths import slugify_project


def test_exclusive_lock_serializes_concurrent_writers(tmp_path):
    """Contended increments through the lock must not lose updates (mutual exclusion)."""
    lock = tmp_path / ".qiju.lock"
    counter = {"value": 0}
    errors: list[Exception] = []
    threads_n, iters = 4, 40

    def worker() -> None:
        try:
            for _ in range(iters):
                with util.exclusive_lock(lock):
                    current = counter["value"]
                    time.sleep(0.0005)  # widen the race window
                    counter["value"] = current + 1
        except Exception as exc:  # pragma: no cover - surfaced via assert
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert counter["value"] == threads_n * iters


def test_replace_atomic_over_existing_file(tmp_path):
    dst = tmp_path / "record.txt"
    dst.write_text("old", encoding="utf-8")
    src = tmp_path / "record.txt.tmp"
    src.write_text("new", encoding="utf-8")

    util.replace_atomic(src, dst)

    assert dst.read_text(encoding="utf-8") == "new"
    assert not src.exists()


@pytest.mark.parametrize("reserved", ["con", "nul", "aux", "prn", "com1", "lpt9", "CON", "Nul"])
def test_slugify_avoids_windows_reserved_names(reserved):
    slug = slugify_project(reserved)
    assert slug not in {"con", "prn", "aux", "nul", "com1", "lpt9"}
    assert slug  # never empty


@pytest.mark.parametrize("name", ["myproj...", "name . ", "trailing.", "spaced "])
def test_slugify_strips_trailing_dots_and_spaces(name):
    slug = slugify_project(name)
    assert not slug.endswith((".", " "))
    assert slug
