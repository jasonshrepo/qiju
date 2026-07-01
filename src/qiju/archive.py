from __future__ import annotations

import os
import tempfile


from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None  # type: ignore

from . import util


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def read_parquet(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if duckdb is None:
        raise RuntimeError("duckdb is required to read Parquet archives")
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(f"SELECT * FROM read_parquet({_sql_quote(str(path))})").fetchall()
        columns = [desc[0] for desc in con.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        con.close()


def write_parquet_atomic(path: Path, entries: list[dict[str, Any]]) -> None:
    if duckdb is None:
        raise RuntimeError("duckdb is required to write Parquet archives")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, json_tmp = tempfile.mkstemp(prefix=".entries.", suffix=".jsonl", dir=path.parent)
    os.close(fd)
    json_tmp_path = Path(json_tmp)
    parquet_tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        util.write_jsonl_atomic(json_tmp_path, entries)
        con = duckdb.connect(":memory:")
        try:
            con.execute(
                f"""
                COPY (
                    SELECT * FROM read_json_auto({_sql_quote(str(json_tmp_path))})
                )
                TO {_sql_quote(str(parquet_tmp_path))}
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            con.close()
        validated = read_parquet(parquet_tmp_path)
        if len(validated) != len(entries):
            raise RuntimeError(
                f"Parquet validation failed for {parquet_tmp_path}: expected {len(entries)} rows, got {len(validated)}"
            )
        expected_ids = {entry.get("id") for entry in entries}
        validated_ids = {entry.get("id") for entry in validated}
        if validated_ids != expected_ids:
            raise RuntimeError(f"Parquet validation failed for {parquet_tmp_path}: ID set mismatch")
        util.replace_atomic(parquet_tmp_path, path)
    finally:
        for tmp in (json_tmp_path, parquet_tmp_path):
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
