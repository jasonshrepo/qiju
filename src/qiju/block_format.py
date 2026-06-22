from __future__ import annotations

QIJU_BLOCK_START = "<!-- qiju:start -->"
QIJU_BLOCK_END = "<!-- qiju:end -->"
CLAUDE_BLOCK_START = "====qiju start ===="
CLAUDE_BLOCK_STOP_PREFIX = "====qiju stop line:"


def find_line_marked_block(content: str) -> tuple[int, int] | None:
    lines = content.splitlines(keepends=True)
    offset = 0
    start_offset: int | None = None
    for line in lines:
        stripped = line.strip()
        if stripped == CLAUDE_BLOCK_START:
            start_offset = offset
        elif start_offset is not None and stripped.startswith(CLAUDE_BLOCK_STOP_PREFIX):
            return start_offset, offset + len(line)
        offset += len(line)
    return None
