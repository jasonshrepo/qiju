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
cat > "$root/.venv/bin/kedu" <<'SH'
#!/usr/bin/env bash
exec "{sys.executable}" "__KEDU_ROOT__/scripts/kedu.py" "$@"
SH
sed -i.bak "s#__KEDU_ROOT__#$root#g" "$root/.venv/bin/kedu"
rm -f "$root/.venv/bin/kedu.bak"
chmod 0755 "$root/.venv/bin/kedu"
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

    kedu_home = tmp_path / "home" / ".kedu"
    bin_dir = tmp_path / "bin"
    install_root = tmp_path / "install-root" / "kedu"
    result = subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "--kedu-home",
            str(kedu_home),
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
    config = json.loads((project / ".kedu" / "config.json").read_text(encoding="utf-8"))
    assert config["enabled_agents"] == ["codex", "cursor"]
    assert (project / ".kedu" / "STATE.md").exists()
    assert (project / ".kedu" / "short.jsonl").exists()
    assert not (project / "AGENTS.md").exists()
    assert (project / ".agents" / "skills" / "kedu" / "SKILL.md").exists()
    assert (project / ".cursor" / "rules" / "kedu.mdc").exists()
    assert ".kedu/" in (git_info / "exclude").read_text(encoding="utf-8")
