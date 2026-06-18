---
name: Host integration issue
about: A host (Claude, Codex, Kiro, Cursor) didn't discover or run Qiju correctly
title: "[host] "
labels: ["host-integration", "developer-preview"]
---

**Host**
Which agent and surface:
- [ ] Claude Code (CLI / desktop)
- [ ] Codex (CLI / desktop)
- [ ] Kiro (CLI / IDE)
- [ ] Cursor (CLI / desktop)
- Host version:

**What happened**
e.g. the agent didn't find Qiju, didn't read `.qiju/STATE.md`, answered from the summary
instead of searching, or couldn't run `qiju log`/`qiju search`.

**How you invoked it**
The prompt or command you used (`/qiju …`, `$qiju …`, or natural language).

**Expected vs actual**
- Expected:
- Actual:

**Setup**
- Output of `qiju init --host <host>` (or how you wired it):
- Does `qiju search --scope current_project --query "…"` work directly in a terminal?
- `qiju --version`:

**Anything else**
Transcript snippet, screenshots, or the generated host files (`.kiro/…`, `.claude/…`, etc.).
