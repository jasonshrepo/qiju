from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"


def write_fake_uv(fake_bin: Path) -> None:
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
if [ "${{1:-}}" != "sync" ]; then
  echo "unexpected uv command: $*" >&2
  exit 2
fi
root="$(pwd)"
mkdir -p "$root/.venv/bin"
cat > "$root/.venv/bin/qiju" <<'SH'
#!/usr/bin/env bash
exec "{sys.executable}" -c "import sys; sys.path.insert(0,'__QIJU_ROOT__/src'); from qiju.cli import main; raise SystemExit(main())" "$@"
SH
sed -i.bak "s#__QIJU_ROOT__#$root#g" "$root/.venv/bin/qiju"
rm -f "$root/.venv/bin/qiju.bak"
chmod 0755 "$root/.venv/bin/qiju"
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)


def test_batch_install_codex_and_cursor_route_through_init(tmp_path):
    fake_bin = tmp_path / "fake-bin"
    write_fake_uv(fake_bin)

    project = tmp_path / "project"
    project.mkdir()
    git_info = project / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text("# local excludes\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    qiju_home = tmp_path / "home" / ".qiju"
    bin_dir = tmp_path / "bin"
    install_root = tmp_path / "install-root" / "qiju"
    result = subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "--qiju-home",
            str(qiju_home),
            "--bin-dir",
            str(bin_dir),
            "--prefix",
            str(install_root),
            "--project",
            str(project),
            "--agents",
            "codex,cursor",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads((project / ".qiju" / "config.json").read_text(encoding="utf-8"))
    assert config["enabled_agents"] == ["codex", "cursor"]
    assert (project / ".qiju" / "short.jsonl").exists()
    assert not (project / "AGENTS.md").exists()
    assert (project / ".agents" / "skills" / "qiju-log" / "SKILL.md").exists()
    assert (project / ".agents" / "skills" / "qiju-search" / "SKILL.md").exists()
    assert (project / ".agents" / "skills" / "qiju-review" / "SKILL.md").exists()
    assert (project / ".cursor" / "skills" / "qiju-log" / "SKILL.md").exists()
    assert (project / ".cursor" / "skills" / "qiju-search" / "SKILL.md").exists()
    assert (project / ".cursor" / "skills" / "qiju-review" / "SKILL.md").exists()
    assert not (project / ".cursor" / "rules" / "qiju.mdc").exists()
    assert ".qiju/" in (git_info / "exclude").read_text(encoding="utf-8")


def test_reinstall_prunes_stale_engine_files_but_preserves_records_and_venv(tmp_path):
    fake_bin = tmp_path / "fake-bin"
    write_fake_uv(fake_bin)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    qiju_home = tmp_path / "home" / ".qiju"
    bin_dir = tmp_path / "bin"
    install_root = tmp_path / "install-root" / "qiju"

    def run_install():
        return subprocess.run(
            [
                "bash",
                str(INSTALL_SH),
                "--qiju-home",
                str(qiju_home),
                "--bin-dir",
                str(bin_dir),
                "--prefix",
                str(install_root),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )

    first = run_install()
    assert first.returncode == 0, first.stdout + first.stderr

    # Plant a stale engine file (removed in a "newer" version) and a record.
    stale = install_root / "scripts" / "_stale_module.py"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("# stale\n", encoding="utf-8")
    record = qiju_home / "long" / "old.jsonl"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text('{"id": "old"}\n', encoding="utf-8")
    venv_marker = install_root / ".venv" / "bin" / "qiju"
    assert venv_marker.exists()

    second = run_install()
    assert second.returncode == 0, second.stdout + second.stderr

    # Stale engine file is pruned; record store and venv survive.
    assert not stale.exists()
    assert record.exists()
    assert record.read_text(encoding="utf-8") == '{"id": "old"}\n'
    assert venv_marker.exists()


def test_missing_option_value_dies_non_zero(tmp_path):
    env = os.environ.copy()
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--prefix"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "option --prefix requires a value" in result.stderr
