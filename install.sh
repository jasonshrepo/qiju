#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${QIJU_BIN_DIR:-$HOME/.local/bin}"
QIJU_HOME="${QIJU_HOME:-$HOME/.qiju}"
INSTALL_ROOT="${QIJU_INSTALL_ROOT:-}"
PROJECT_DIR="${QIJU_PROJECT_DIR:-}"
AGENTS="${QIJU_AGENTS:-none}"
DRY_RUN=0
PROJECT_EXPLICIT=0
INSTALL_LAUNCHD=0
LAUNCHD_LABEL="${QIJU_LAUNCHD_LABEL:-org.qiju.maintain}"

usage() {
  cat <<'USAGE'
Qiju installer

Usage:
  bash install.sh [options]

Options:
  --prefix PATH        Install engine files here (default: <qiju-home>/qiju)
  --bin-dir PATH       Install qiju shim here (default: ~/.local/bin)
  --qiju-home PATH     Shared Qiju store (default: ~/.qiju)
  --project PATH       Project/workspace path for project-local agent files
  --agents LIST        Optional batch agent setup: all or comma list: claude,kiro,codex,cursor
  --install-launchd    Install macOS LaunchAgent for scheduled maintenance
  --dry-run            Print actions without writing files
  -h, --help           Show this help

Examples:
  bash install.sh
  cd /path/to/repo && qiju init --host codex
  qiju init --host codex --global  # optional later

Batch mode is still available:
  bash install.sh --agents claude
  bash install.sh --agents kiro,codex --project /path/to/repo
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

require_arg() {
  # $1 = option name, $2 = the value (may be unset)
  [ "$#" -ge 2 ] && [ -n "${2:-}" ] || die "option $1 requires a value"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] %q' "$1"
    shift || true
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

script_dir() {
  local source="${BASH_SOURCE[0]}"
  while [ -h "$source" ]; do
    local dir
    dir="$(cd -P "$(dirname "$source")" >/dev/null 2>&1 && pwd)"
    source="$(readlink "$source")"
    [[ "$source" != /* ]] && source="$dir/$source"
  done
  cd -P "$(dirname "$source")" >/dev/null 2>&1 && pwd
}

SOURCE_DIR="$(script_dir)"
VERSION="$(grep -m1 '^version' "$SOURCE_DIR/pyproject.toml" | cut -d'"' -f2)"

if [ -n "${QIJU_PROJECT_DIR:-}" ]; then
  PROJECT_EXPLICIT=1
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      require_arg "$1" "${2:-}"
      INSTALL_ROOT="$2"
      shift 2
      ;;
    --bin-dir)
      require_arg "$1" "${2:-}"
      BIN_DIR="$2"
      shift 2
      ;;
    --qiju-home)
      require_arg "$1" "${2:-}"
      QIJU_HOME="$2"
      shift 2
      ;;
    --project)
      require_arg "$1" "${2:-}"
      PROJECT_DIR="$2"
      PROJECT_EXPLICIT=1
      shift 2
      ;;
    --agents)
      require_arg "$1" "${2:-}"
      AGENTS="$2"
      shift 2
      ;;
    --install-launchd)
      INSTALL_LAUNCHD=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

BIN_DIR="${BIN_DIR/#\~/$HOME}"
QIJU_HOME="${QIJU_HOME/#\~/$HOME}"
if [ -z "$INSTALL_ROOT" ]; then
  INSTALL_ROOT="$QIJU_HOME/qiju"
else
  INSTALL_ROOT="${INSTALL_ROOT/#\~/$HOME}"
fi
if [ -n "$PROJECT_DIR" ]; then
  PROJECT_DIR="${PROJECT_DIR/#\~/$HOME}"
fi

looks_like_project() {
  local candidate="$1"
  [ -d "$candidate/.git" ] ||
    [ -d "$candidate/.kiro" ] ||
    [ -d "$candidate/.cursor" ] ||
    [ -f "$candidate/AGENTS.md" ] ||
    [ -f "$candidate/CLAUDE.md" ]
}

if [ -z "$PROJECT_DIR" ] && [ "$PROJECT_EXPLICIT" -eq 0 ]; then
  CWD="$(pwd)"
  if [ "$CWD" != "$SOURCE_DIR" ] && looks_like_project "$CWD"; then
    PROJECT_DIR="$CWD"
  fi
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

same_file() {
  [ -f "$1" ] && [ -f "$2" ] && cmp -s "$1" "$2"
}

backup_path() {
  printf '%s.bak.%s' "$1" "$(date +%Y%m%d%H%M%S)"
}

install_file() {
  local src="$1"
  local dst="$2"
  local mode="${3:-0644}"
  [ -f "$src" ] || die "missing source file: $src"
  if same_file "$src" "$dst"; then
    log "ok: $dst"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] install $src -> $dst"
    return 0
  fi
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    local backup
    backup="$(backup_path "$dst")"
    cp "$dst" "$backup"
    log "backup: $dst -> $backup"
  fi
  cp "$src" "$dst"
  chmod "$mode" "$dst"
  log "installed: $dst"
}

clean_install_root() {
  [ -d "$INSTALL_ROOT" ] || return 0
  # Guard against deleting the record store: refuse if QIJU_HOME is the install
  # root or lives inside it. In the default layout INSTALL_ROOT=$QIJU_HOME/qiju,
  # so the record store under $QIJU_HOME is a SIBLING of the install root and
  # this guard passes (pruning is safe).
  case "$QIJU_HOME/" in
    "$INSTALL_ROOT"/*)
      die "refusing to reinstall: qiju home ($QIJU_HOME) is inside the engine path ($INSTALL_ROOT); use a separate --prefix or --qiju-home"
      ;;
  esac
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] prune $INSTALL_ROOT"
    return 0
  fi
  # Remove every top-level entry except the venv, so files dropped in a newer
  # version do not linger; keeping .venv keeps uv sync --frozen a fast no-op.
  find "$INSTALL_ROOT" -mindepth 1 -maxdepth 1 ! -name '.venv' -exec rm -rf {} +
}

copy_project() {
  require_command tar
  log "Installing Qiju $VERSION"
  log "source: $SOURCE_DIR"
  log "target: $INSTALL_ROOT"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] copy project files"
    return 0
  fi
  clean_install_root
  mkdir -p "$INSTALL_ROOT"
  (
    cd "$SOURCE_DIR"
    tar \
      --exclude './*.egg-info' \
      --exclude './.git' \
      -cf - .
  ) | (
    cd "$INSTALL_ROOT"
    tar -xf -
  )
}

sync_python_env() {
  require_command uv
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] uv sync --frozen --no-dev"
    return 0
  fi
  (
    cd "$INSTALL_ROOT"
    uv sync --frozen --no-dev
  )
}

install_qiju_shim() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] write $BIN_DIR/qiju"
    return 0
  fi
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/qiju" <<EOF
#!/usr/bin/env bash
export QIJU_HOME="\${QIJU_HOME:-$QIJU_HOME}"
exec "$INSTALL_ROOT/.venv/bin/qiju" "\$@"
EOF
  chmod 0755 "$BIN_DIR/qiju"
  log "installed: $BIN_DIR/qiju"
}

install_shared_store() {
  run mkdir -p "$QIJU_HOME/long" "$QIJU_HOME/archive" "$QIJU_HOME/adapters" "$QIJU_HOME/agents" "$QIJU_HOME/logs"
  install_file "$SOURCE_DIR/adapters/claude_code.sh" "$QIJU_HOME/adapters/claude_code.sh" 0755
  install_file "$SOURCE_DIR/skills/qiju-log/SKILL.md" "$QIJU_HOME/agents/qiju-log-skill.md" 0644
  install_file "$SOURCE_DIR/skills/qiju-search/SKILL.md" "$QIJU_HOME/agents/qiju-search-skill.md" 0644
  install_file "$SOURCE_DIR/skills/qiju-review/SKILL.md" "$QIJU_HOME/agents/qiju-review-skill.md" 0644
}

install_launchd() {
  if [ "$(uname -s)" != "Darwin" ]; then
    log "skip: launchd maintenance is only available on macOS"
    return 0
  fi

  local target_dir="$HOME/Library/LaunchAgents"
  local target_plist="$target_dir/$LAUNCHD_LABEL.plist"
  local qiju_bin="$INSTALL_ROOT/.venv/bin/qiju"
  local log_dir="$QIJU_HOME/logs"

  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] write $target_plist"
    log "[dry-run] launchctl unload/load $target_plist"
    return 0
  fi

  mkdir -p "$target_dir" "$log_dir"
  cat > "$target_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LAUNCHD_LABEL</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>QIJU_HOME</key>
    <string>$QIJU_HOME</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>$qiju_bin</string>
    <string>maintain</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$log_dir/qiju-maintain.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/qiju-maintain.err</string>
</dict>
</plist>
EOF

  launchctl unload "$target_plist" >/dev/null 2>&1 || true
  launchctl load "$target_plist"
  log "installed launchd maintenance: $target_plist"
}

has_agent_requested() {
  local name="$1"
  if [ "$AGENTS" = "all" ]; then
    return 0
  fi
  if [ "$AGENTS" = "auto" ] || [ "$AGENTS" = "none" ]; then
    return 1
  fi
  case ",$AGENTS," in
    *",$name,"*) return 0 ;;
    *) return 1 ;;
  esac
}

detect_claude() {
  [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1
}

detect_kiro() {
  [ -n "$PROJECT_DIR" ] || return 1
  [ -d "$PROJECT_DIR/.kiro" ] || [ -d "$HOME/.kiro" ] || command -v kiro >/dev/null 2>&1 || command -v kiro-cli >/dev/null 2>&1
}

detect_codex() {
  [ -n "$PROJECT_DIR" ] || return 1
  [ -d "$HOME/.codex" ] || [ -f "$PROJECT_DIR/AGENTS.md" ] || command -v codex >/dev/null 2>&1
}

detect_cursor() {
  [ -n "$PROJECT_DIR" ] || return 1
  [ -d "$PROJECT_DIR/.cursor" ] || [ -d "$HOME/.cursor" ] || command -v cursor >/dev/null 2>&1
}

is_project_scoped_agent() {
  case "$1" in
    kiro|codex|cursor) return 0 ;;
    *) return 1 ;;
  esac
}

should_install_agent() {
  local name="$1"
  if has_agent_requested "$name"; then
    return 0
  fi
  if [ "$AGENTS" != "auto" ]; then
    return 1
  fi
  "detect_$name"
}

install_claude() {
  log "Installing Claude Code integration"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] qiju init --host claude --global"
  else
    QIJU_HOME="$QIJU_HOME" QIJU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/qiju" init --host claude --global >/dev/null
  fi
  if [ -n "$PROJECT_DIR" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      log "[dry-run] cd $PROJECT_DIR && qiju init --host claude"
    else
      (cd "$PROJECT_DIR" && QIJU_HOME="$QIJU_HOME" QIJU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/qiju" init --host claude >/dev/null)
    fi
  fi
  log "Claude integration registered through Qiju init"
}

install_kiro() {
  [ -n "$PROJECT_DIR" ] || die "Kiro integration requires --project"
  log "Installing Kiro integration for project: $PROJECT_DIR"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] cd $PROJECT_DIR && qiju init --host kiro"
  else
    (cd "$PROJECT_DIR" && QIJU_HOME="$QIJU_HOME" QIJU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/qiju" init --host kiro >/dev/null)
  fi
}

install_codex() {
  [ -n "$PROJECT_DIR" ] || die "Codex integration requires --project"
  log "Installing Codex integration for project: $PROJECT_DIR"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] cd $PROJECT_DIR && qiju init --host codex"
  else
    (cd "$PROJECT_DIR" && QIJU_HOME="$QIJU_HOME" QIJU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/qiju" init --host codex >/dev/null)
  fi
}

install_cursor() {
  [ -n "$PROJECT_DIR" ] || die "Cursor integration requires --project"
  log "Installing Cursor integration for project: $PROJECT_DIR"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] cd $PROJECT_DIR && qiju init --host cursor"
  else
    (cd "$PROJECT_DIR" && QIJU_HOME="$QIJU_HOME" QIJU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/qiju" init --host cursor >/dev/null)
  fi
}

print_status() {
  log ""
  log "Install status"
  log "  qiju home:  $QIJU_HOME"
  log "  engine path:  $INSTALL_ROOT"
  log "  qiju CLI:   $BIN_DIR/qiju"
  if [ -n "$PROJECT_DIR" ]; then
    log "  project path: $PROJECT_DIR"
  else
    log "  project path: (none; project-local integrations skipped)"
  fi
  if command -v "$BIN_DIR/qiju" >/dev/null 2>&1 || [ -x "$BIN_DIR/qiju" ]; then
    log "  cli check:    ok"
  else
    log "  cli check:    add $BIN_DIR to PATH"
  fi
}

migrate_legacy_kedu() {
  # One-time, lossless brand migration: if a legacy ~/.kedu record store exists, copy
  # it into the new QIJU_HOME (rewriting kedu->qiju in every record). The legacy store
  # is left untouched as a backup; the migration is idempotent (sentinel-guarded).
  local legacy_home="$HOME/.kedu"
  if [ ! -d "$legacy_home" ]; then
    log "skip: no legacy ~/.kedu store to migrate"
    return 0
  fi
  if [ "$legacy_home" = "$QIJU_HOME" ]; then
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] qiju migrate --from-kedu (legacy store: $legacy_home -> $QIJU_HOME)"
    return 0
  fi
  log "Migrating legacy Kedu records: $legacy_home -> $QIJU_HOME"
  if QIJU_HOME="$QIJU_HOME" "$INSTALL_ROOT/.venv/bin/qiju" migrate --from-kedu \
       --project-root "${PROJECT_DIR:-$PWD}" >/dev/null; then
    log "migration complete (legacy ~/.kedu preserved as backup)"
  else
    log "warning: kedu->qiju record migration reported an error; legacy ~/.kedu is intact"
  fi
}

main() {
  copy_project
  sync_python_env
  install_qiju_shim
  install_shared_store
  migrate_legacy_kedu
  if [ "$INSTALL_LAUNCHD" -eq 1 ]; then
    install_launchd
  fi

  local installed_any_agent=0
  for agent_name in claude kiro codex cursor; do
    if should_install_agent "$agent_name"; then
      if is_project_scoped_agent "$agent_name" && [ -z "$PROJECT_DIR" ]; then
        log "skip: $agent_name integration requires --project; template installed under $QIJU_HOME/agents"
        continue
      fi
      "install_$agent_name"
      installed_any_agent=1
    else
      log "skip: $agent_name integration not detected/requested"
    fi
  done

  if [ "$installed_any_agent" -eq 0 ]; then
    log "no agent integrations installed by install.sh"
    log "next: cd into a project and run 'qiju init --host <claude|kiro|codex|cursor>'"
    log "optional later: run 'qiju init --host <host> --global' for user-level defaults"
  fi
  print_status
}

main "$@"
