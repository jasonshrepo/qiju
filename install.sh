#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.0"
BIN_DIR="${KEDU_BIN_DIR:-$HOME/.local/bin}"
KEDU_HOME="${KEDU_HOME:-$HOME/.kedu}"
INSTALL_ROOT="${KEDU_INSTALL_ROOT:-}"
PROJECT_DIR="${KEDU_PROJECT_DIR:-}"
AGENTS="${KEDU_AGENTS:-none}"
DRY_RUN=0
PROJECT_EXPLICIT=0
INSTALL_LAUNCHD=0
LAUNCHD_LABEL="${KEDU_LAUNCHD_LABEL:-org.kedu.maintain}"

usage() {
  cat <<'USAGE'
Kedu installer

Usage:
  bash install.sh [options]

Options:
  --prefix PATH        Install engine files here (default: <kedu-home>/kedu)
  --bin-dir PATH       Install kedu shim here (default: ~/.local/bin)
  --kedu-home PATH     Shared Kedu store (default: ~/.kedu)
  --project PATH       Project/workspace path for project-local agent files
  --agents LIST        Optional batch agent setup: all or comma list: claude,kiro,codex,cursor
  --install-launchd    Install macOS LaunchAgent for scheduled maintenance
  --dry-run            Print actions without writing files
  -h, --help           Show this help

Examples:
  bash install.sh
  cd /path/to/repo && kedu init --host codex
  kedu init --host codex --global  # optional later

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

if [ -n "${KEDU_PROJECT_DIR:-}" ]; then
  PROJECT_EXPLICIT=1
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      INSTALL_ROOT="$2"
      shift 2
      ;;
    --bin-dir)
      BIN_DIR="$2"
      shift 2
      ;;
    --kedu-home)
      KEDU_HOME="$2"
      shift 2
      ;;
    --project)
      PROJECT_DIR="$2"
      PROJECT_EXPLICIT=1
      shift 2
      ;;
    --agents)
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
KEDU_HOME="${KEDU_HOME/#\~/$HOME}"
if [ -z "$INSTALL_ROOT" ]; then
  INSTALL_ROOT="$KEDU_HOME/kedu"
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

append_block_if_missing() {
  local block_file="$1"
  local target_file="$2"
  local marker="$3"
  if [ -f "$target_file" ] && grep -q "$marker" "$target_file"; then
    log "ok: $target_file already contains kedu block"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] append $block_file -> $target_file"
    return 0
  fi
  mkdir -p "$(dirname "$target_file")"
  if [ -e "$target_file" ]; then
    local backup
    backup="$(backup_path "$target_file")"
    cp "$target_file" "$backup"
    log "backup: $target_file -> $backup"
    printf '\n\n' >> "$target_file"
  fi
  cat "$block_file" >> "$target_file"
  printf '\n' >> "$target_file"
  log "updated: $target_file"
}

copy_project() {
  require_command tar
  log "Installing Kedu $VERSION"
  log "source: $SOURCE_DIR"
  log "target: $INSTALL_ROOT"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] copy project files"
    return 0
  fi
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

install_kedu_shim() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] write $BIN_DIR/kedu"
    return 0
  fi
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/kedu" <<EOF
#!/usr/bin/env bash
export KEDU_HOME="\${KEDU_HOME:-$KEDU_HOME}"
exec "$INSTALL_ROOT/.venv/bin/kedu" "\$@"
EOF
  chmod 0755 "$BIN_DIR/kedu"
  log "installed: $BIN_DIR/kedu"
}

install_shared_store() {
  run mkdir -p "$KEDU_HOME/long" "$KEDU_HOME/archive" "$KEDU_HOME/hooks" "$KEDU_HOME/adapters" "$KEDU_HOME/agents" "$KEDU_HOME/logs"
  install_file "$SOURCE_DIR/hooks/session_end_log.sh" "$KEDU_HOME/hooks/session_end_log.sh" 0755
  install_file "$SOURCE_DIR/adapters/claude_code.sh" "$KEDU_HOME/adapters/claude_code.sh" 0755
  install_file "$SOURCE_DIR/agents/claude/CLAUDE.kedu.md" "$KEDU_HOME/agents/claude-CLAUDE.kedu.md" 0644
  install_file "$SOURCE_DIR/skills/kedu/SKILL.md" "$KEDU_HOME/agents/claude-kedu-skill.md" 0644
  install_file "$SOURCE_DIR/agents/codex/AGENTS.kedu.md" "$KEDU_HOME/agents/codex-AGENTS.kedu.md" 0644
  install_file "$SOURCE_DIR/agents/kiro/steering/kedu.md" "$KEDU_HOME/agents/kiro-kedu.md" 0644
  install_file "$SOURCE_DIR/agents/kiro/hooks/kedu-clean-exit.kiro.hook" "$KEDU_HOME/agents/kiro-kedu-clean-exit.kiro.hook" 0644
  install_file "$SOURCE_DIR/agents/kiro/agents/kedu.json" "$KEDU_HOME/agents/kiro-kedu-agent.json" 0644
  install_file "$SOURCE_DIR/agents/kiro/prompts/kedu-agent-prompt.md" "$KEDU_HOME/agents/kiro-kedu-agent-prompt.md" 0644
  install_file "$SOURCE_DIR/agents/cursor/rules/kedu.mdc" "$KEDU_HOME/agents/cursor-kedu.mdc" 0644
}

install_launchd() {
  if [ "$(uname -s)" != "Darwin" ]; then
    log "skip: launchd maintenance is only available on macOS"
    return 0
  fi

  local target_dir="$HOME/Library/LaunchAgents"
  local target_plist="$target_dir/$LAUNCHD_LABEL.plist"
  local python_bin="$INSTALL_ROOT/.venv/bin/python"
  local kedu_script="$INSTALL_ROOT/scripts/kedu.py"
  local log_dir="$KEDU_HOME/logs"

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
    <key>KEDU_HOME</key>
    <string>$KEDU_HOME</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>$python_bin</string>
    <string>$kedu_script</string>
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
  <string>$log_dir/kedu-maintain.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/kedu-maintain.err</string>
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
    log "[dry-run] kedu init --host claude --global"
  else
    KEDU_HOME="$KEDU_HOME" KEDU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/kedu" init --host claude --global >/dev/null
  fi
  if [ -n "$PROJECT_DIR" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      log "[dry-run] cd $PROJECT_DIR && kedu init --host claude"
    else
      (cd "$PROJECT_DIR" && KEDU_HOME="$KEDU_HOME" KEDU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/kedu" init --host claude >/dev/null)
    fi
  fi
  log "Claude SessionEnd hook registered through Kedu init"
}

install_kiro() {
  [ -n "$PROJECT_DIR" ] || die "Kiro integration requires --project"
  log "Installing Kiro integration for project: $PROJECT_DIR"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] cd $PROJECT_DIR && kedu init --host kiro"
  else
    (cd "$PROJECT_DIR" && KEDU_HOME="$KEDU_HOME" KEDU_INSTALL_ROOT="$INSTALL_ROOT" "$INSTALL_ROOT/.venv/bin/kedu" init --host kiro >/dev/null)
  fi
}

install_codex() {
  [ -n "$PROJECT_DIR" ] || die "Codex integration requires --project"
  log "Installing Codex integration for project: $PROJECT_DIR"
  append_block_if_missing "$SOURCE_DIR/agents/codex/AGENTS.kedu.md" "$PROJECT_DIR/AGENTS.md" "kedu:start"
}

install_cursor() {
  [ -n "$PROJECT_DIR" ] || die "Cursor integration requires --project"
  log "Installing Cursor integration for project: $PROJECT_DIR"
  install_file "$SOURCE_DIR/agents/cursor/rules/kedu.mdc" "$PROJECT_DIR/.cursor/rules/kedu.mdc" 0644
}

print_status() {
  log ""
  log "Install status"
  log "  kedu home:  $KEDU_HOME"
  log "  engine path:  $INSTALL_ROOT"
  log "  kedu CLI:   $BIN_DIR/kedu"
  if [ -n "$PROJECT_DIR" ]; then
    log "  project path: $PROJECT_DIR"
  else
    log "  project path: (none; project-local integrations skipped)"
  fi
  if command -v "$BIN_DIR/kedu" >/dev/null 2>&1 || [ -x "$BIN_DIR/kedu" ]; then
    log "  cli check:    ok"
  else
    log "  cli check:    add $BIN_DIR to PATH"
  fi
}

main() {
  copy_project
  sync_python_env
  install_kedu_shim
  install_shared_store
  if [ "$INSTALL_LAUNCHD" -eq 1 ]; then
    install_launchd
  fi

  local installed_any_agent=0
  for agent_name in claude kiro codex cursor; do
    if should_install_agent "$agent_name"; then
      if is_project_scoped_agent "$agent_name" && [ -z "$PROJECT_DIR" ]; then
        log "skip: $agent_name integration requires --project; template installed under $KEDU_HOME/agents"
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
    log "next: cd into a project and run 'kedu init --host <claude|kiro|codex|cursor>'"
    log "optional later: run 'kedu init --host <host> --global' for user-level defaults"
  fi
  print_status
}

main "$@"
