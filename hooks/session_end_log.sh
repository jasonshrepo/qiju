#!/usr/bin/env bash
set -euo pipefail

# Best-effort Claude Code SessionEnd adapter.
#
# Claude Code passes hook metadata on stdin. This script reads that metadata without
# blocking an agent shell forever, extracts the session id when present, and avoids
# duplicate clean-exit records. A bare shell hook still cannot summarize the live model
# context on its own; use the kedu-log skill or a host ask-agent adapter for the actual
# structured entry.

KEDU_HOME="${KEDU_HOME:-$HOME/.kedu}"
PYTHON_BIN="${KEDU_PYTHON:-$KEDU_HOME/kedu/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

read_hook_json() {
  local first=""
  local line=""
  local payload=""
  if IFS= read -r -t 2 first; then
    payload="$first"
    while IFS= read -r -t 1 line; do
      payload="${payload}"$'\n'"${line}"
    done
  fi
  printf '%s' "$payload"
}

json_field() {
  local field="$1"
  [ -n "$HOOK_JSON" ] || return 0
  [ -n "$PYTHON_BIN" ] || return 0
  HOOK_JSON_VALUE="$HOOK_JSON" "$PYTHON_BIN" - "$field" <<'PY' 2>/dev/null || true
import json
import os
import sys

field = sys.argv[1]
raw = os.environ.get("HOOK_JSON_VALUE", "")
if not raw.strip():
    raise SystemExit(0)
data = json.loads(raw)
value = data.get(field)
if value is None:
    aliases = {
        "session_id": ("sessionId", "sessionID"),
        "cwd": ("workspace_dir", "workspace", "project_dir"),
    }
    for alias in aliases.get(field, ()):
        value = data.get(alias)
        if value is not None:
            break
if value is not None:
    print(value)
PY
}

HOOK_JSON="$(read_hook_json)"
JSON_SESSION_ID="$(json_field session_id)"
JSON_CWD="$(json_field cwd)"

SESSION_ID="${JSON_SESSION_ID:-${CLAUDE_SESSION_ID:-${KEDU_SESSION_ID:-${KIRO_SESSION_ID:-}}}}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="hook-$(date +%s)"
fi

PROJECT_DIR="${JSON_CWD:-$PWD}"
PROJECT="${KEDU_PROJECT:-$(basename "$PROJECT_DIR")}"
AGENT="${KEDU_AGENT:-claude}"
LONG_FILE="$KEDU_HOME/long/${PROJECT}.jsonl"

if [ -f "$LONG_FILE" ] && grep -q "\"id\"[[:space:]]*:[[:space:]]*\"$SESSION_ID:" "$LONG_FILE"; then
  exit 0
fi

echo "kedu SessionEnd hook: no structured record supplied for session=$SESSION_ID agent=$AGENT; use kedu-log or a host ask-agent adapter" >&2
exit 0
