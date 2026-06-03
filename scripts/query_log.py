from __future__ import annotations

import sys
from typing import Any

try:
    from . import paths as paths_mod, redact, util
except ImportError:  # pragma: no cover
    import paths as paths_mod  # type: ignore
    import redact  # type: ignore
    import util  # type: ignore


def log_query(
    *,
    scope: str,
    project_filter: list[str],
    query: str | None,
    filters: dict[str, Any],
    result_count: int,
) -> None:
    try:
        kedu_paths = paths_mod.resolve_paths(project=project_filter[0] if project_filter else None)
        event = {
            "ts": util.utcish_now_iso(),
            "scope": scope,
            "project_filter": project_filter,
            "query": query or "",
            "filters": filters,
            "result_count": result_count,
        }
        redacted, _ = redact.redact_value(event, "query_log")
        util.append_jsonl(kedu_paths.query_log, redacted)
    except Exception as exc:
        print(f"warning: failed to write query log: {exc}", file=sys.stderr)
