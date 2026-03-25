#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "oss_framework" / "data" / "oea.duckdb"
DB_PATH = Path(os.getenv("DUCKDB_DATABASE_PATH", str(DEFAULT_DB)))
MANIFEST_PATH = Path(__file__).resolve().with_name("contract_query_manifest.json")

JSON_FILES = [
    ROOT / "schema" / "chronic_absenteeism_definition.json",
    ROOT / "schema" / "equity_outcomes_definition.json",
    ROOT / "schema" / "class_effectiveness_definition.json",
    ROOT / "schema" / "performance_correlations_definition.json",
    ROOT / "schema" / "wellbeing_risk_definition.json",
]

def load_query_manifest() -> list[tuple[str, str]]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing query manifest: {MANIFEST_PATH}")

    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Query manifest must be a JSON array")

    queries: list[tuple[str, str]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Manifest item {index} must be an object")
        name = item.get("name")
        query = item.get("query")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Manifest item {index} has invalid name")
        if not isinstance(query, str) or not query:
            raise ValueError(f"Manifest item {index} has invalid query")
        queries.append((name, query))

    return queries


def validate_json_files() -> list[str]:
    errors: list[str] = []
    for path in JSON_FILES:
        if not path.exists():
            errors.append(f"Missing JSON definition: {path}")
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        except Exception as exc:
            errors.append(f"Invalid JSON {path}: {exc}")
    return errors


def run_queries() -> tuple[list[str], int]:
    errors: list[str] = []
    if not DB_PATH.exists():
        return [f"DuckDB file not found: {DB_PATH}"], 0

    try:
        queries = load_query_manifest()
    except Exception as exc:
        return [f"Failed to load query manifest: {exc}"], 0

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for name, query in queries:
            try:
                conn.execute(query).fetchall()
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    finally:
        conn.close()
    return errors, len(queries)


def main() -> int:
    json_errors = validate_json_files()
    query_errors, query_count = run_queries()

    if json_errors:
        print("JSON validation failures:")
        for err in json_errors:
            print(f"- {err}")

    if query_errors:
        print("Query contract failures:")
        for err in query_errors:
            print(f"- {err}")

    if json_errors or query_errors:
        print(f"Contract tests failed (json={len(json_errors)}, query={len(query_errors)})")
        return 1

    print(f"Contract tests passed ({query_count} queries, {len(JSON_FILES)} JSON files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
