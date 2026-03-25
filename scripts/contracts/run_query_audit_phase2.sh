#!/usr/bin/env bash
set +e
DB="oss_framework/data/oea.duckdb"
OUT="DataAnalysisExpert/query_audit_phase2"
MANIFEST="scripts/contracts/contract_query_manifest.json"
mkdir -p "$OUT"
SUMMARY="$OUT/summary.txt"
: > "$SUMMARY"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Missing query manifest: $MANIFEST"
  exit 1
fi

audit_query() {
  local name="$1"
  local sql="$2"
  local safe
  safe=$(echo "$name" | tr ' /' '__')
  local logfile="$OUT/${safe}.log"
  duckdb "$DB" -c "$sql" > "$logfile" 2>&1
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    echo "PASS|$name|$logfile" >> "$SUMMARY"
  else
    echo "FAIL|$name|$logfile" >> "$SUMMARY"
  fi
}

while IFS=$'\t' read -r name sql; do
  audit_query "$name" "$sql"
done < <(
  python3 - <<'PY'
import json
from pathlib import Path

manifest = Path("scripts/contracts/contract_query_manifest.json")
with manifest.open("r", encoding="utf-8") as handle:
    payload = json.load(handle)

for item in payload:
    name = item["name"]
    query = item["query"].replace("\n", " ").strip()
    print(f"{name}\t{query}")
PY
)

echo "Wrote $SUMMARY"
