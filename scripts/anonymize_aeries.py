#!/usr/bin/env python3
"""
anonymize_aeries.py — Strip PII from Aeries SIS test data and output anonymized files.

Reads from: ~/Desktop/AeRIES test data/  (source — contains real student PII)
Writes to:  data/aeries_anonymized/     (output — safe for warehouse loading)

Anonymization rules (per AERIES_DATA_INVENTORY.md):
  1. Hash StudentID (and all student identifiers) with SHA-256 + fixed salt
  2. Hash staff IDs with a separate salt
  3. Drop name, DOB, address, phone, email, login fields entirely
  4. NULL out free-text fields (Comment, ShortDescription, Initials, etc.)
  5. Drop unknown UserCode fields
  6. Strip whitespace on all fields (critical for 2022-23 file)
  7. Preserve all analytical columns

Uses _transformed/ files where available (already flattened from raw JSON).
Outputs CSV (Parquet if pyarrow is available).
"""

from __future__ import annotations

import hashlib
import json
import os
import csv
import re
import sys
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────

# Source and output paths
SOURCE_DIR = Path.home() / "Desktop" / "AeRIES test data"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "aeries_anonymized"

# Salts (fixed for deterministic hashing across files — enables joins)
STUDENT_SALT = "aeries_student_2026_salt_v1"
STAFF_SALT = "aeries_staff_2026_salt_v1"

# ── Column classification ──────────────────────────────────────────────

# Columns to hash with student salt (same function → same hash → joins work)
STUDENT_ID_COLUMNS = {
    "StudentID", "Admin_StudentID", "OldStudentID",
    "StateStudentID", "StudentNumber",
}

# Columns to hash with staff salt
STAFF_ID_COLUMNS = {
    "CounselorNumber", "HomeRoomTeacherNumber", "ElementaryTeacherNumber",
    "TeacherNumber", "MP_PrimaryStaffID",
}

# Columns to drop entirely (direct PII)
DROP_COLUMNS = {
    # Names
    "LastName", "FirstName", "MiddleName",
    "LastNameAlias", "FirstNameAlias", "MiddleNameAlias",
    "NameSuffix", "ParentGuardianName", "ElementaryTeacherName",
    # DOB
    "Birthdate",
    # Addresses
    "MailingAddress", "MailingAddressCity", "MailingAddressState",
    "MailingAddressZipCode", "MailingAddressZipExt",
    "ResidenceAddress", "ResidenceAddressCity", "ResidenceAddressState",
    "ResidenceAddressZipCode", "ResidenceAddressZipExt",
    # Phones
    "HomePhone", "StudentMobilePhone",
    # Emails
    "StudentPersonalEmailAddress", "ParentEmailAddress",
    "StudentEmailAddress",
    # Login
    "NetworkLoginID",
    # Quasi-PII
    "LockerNumber", "FamilyKey",
}

# Free-text columns to null out (keep column, set value to empty string)
NULL_TEXT_COLUMNS = {
    "Comment", "ShortDescription", "ReferredByOther", "Initials",
    "MP_Comment1Code", "MP_Comment2Code", "MP_Comment3Code",
}

# UserCode columns to drop (unknown content, default to drop)
USER_CODE_COLUMNS = {f"UserCode{i}" for i in range(1, 14)}

# Subdirectory → file pattern mapping
# Uses _transformed/ where available (already flattened)
SOURCE_MAP = {
    "students": {"pattern": "students_*.csv", "subdir": "students"},
    "attendance": {"pattern": "attendance_*.csv", "subdir": "attendance_transformed"},
    "discipline": {"pattern": "discipline_*.csv", "subdir": "discipline_transformed"},
    "enrollment": {"pattern": "enrollment_*.csv", "subdir": "enrollment"},
    "grades_gpa": {"pattern": "gpa_*.csv", "subdir": "grades_gpa"},
    "grades": {"pattern": "grades_*.csv", "subdir": "grades_transformed"},
    "programs": {"pattern": "programs_*.csv", "subdir": "programs"},
}


# ── Hashing ────────────────────────────────────────────────────────────

def hash_student_id(value: str) -> str:
    """SHA-256 hash of student ID with student salt. Deterministic across files."""
    if not value or not value.strip():
        return ""
    return hashlib.sha256(f"{STUDENT_SALT}:{value.strip()}".encode()).hexdigest()[:32]


def hash_staff_id(value: str) -> str:
    """SHA-256 hash of staff ID with staff salt. Deterministic across files."""
    if not value or not value.strip():
        return ""
    return hashlib.sha256(f"{STAFF_SALT}:{value.strip()}".encode()).hexdigest()[:32]


# ── File discovery (works around macOS TCC on ~/Desktop) ──────────────

def list_source_files() -> dict[str, list[Path]]:
    """Find all source CSV files, grouped by output category.

    Tries os.listdir first; falls back to AppleScript if TCC blocks shell.
    """
    files = {}
    for category, spec in SOURCE_MAP.items():
        subdir = SOURCE_DIR / spec["subdir"]
        pattern = spec["pattern"]
        try:
            matched = sorted(subdir.glob(pattern))
            if matched:
                files[category] = matched
                continue
        except PermissionError:
            pass

        # Fallback: use osascript to list files
        matched = _list_via_applescript(subdir, pattern)
        if matched:
            files[category] = matched

    return files


def _list_via_applescript(directory: Path, pattern: str) -> list[Path]:
    """List files in a TCC-restricted directory via AppleScript."""
    import subprocess
    try:
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        regex = re.compile(f"^{regex_pattern}$")

        script = f'''
        tell application "System Events"
            set folderPath to "{directory}"
            try
                set fileList to name of every file of folder folderPath
                set AppleScript's text item delimiters to linefeed
                return fileList as text
            on error
                return ""
            end try
        end tell
        '''

        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        names = [n.strip() for n in proc.stdout.strip().split("\n") if n.strip()]
        matched = []
        for name in names:
            if regex.match(name):
                matched.append(directory / name)
        return sorted(matched)
    except Exception:
        return []


def read_csv_rows(file_path: Path) -> tuple[list[str], list[dict]]:
    """Read a CSV file and return (headers, rows as list of dicts).

    Handles the whitespace-padding issue in 2022-23 files by stripping all values.
    """
    import subprocess

    # Try normal file open first
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in reader.fieldnames or []]
            rows = []
            for row in reader:
                stripped = {}
                for k, v in row.items():
                    key = k.strip() if isinstance(k, str) else str(k or "")
                    val = v.strip() if isinstance(v, str) else str(v or "")
                    stripped[key] = val
                rows.append(stripped)
            return headers, rows
    except PermissionError:
        pass

    # Fallback: AppleScript read file
    script = f'''
    set filePath to POSIX file "{file_path}"
    try
        return read filePath as «class utf8»
    on error
        return read filePath
    end try
    '''

    import subprocess
    proc = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    content = proc.stdout

    # Parse CSV from string
    import io
    reader = csv.DictReader(io.StringIO(content))
    headers = [h.strip() for h in reader.fieldnames or []]
    rows = []
    for row in reader:
        stripped = {}
        for k, v in row.items():
            key = k.strip() if isinstance(k, str) else str(k or "")
            val = v.strip() if isinstance(v, str) else str(v or "")
            stripped[key] = val
        rows.append(stripped)
    return headers, rows


# ── Anonymization ─────────────────────────────────────────────────────

def anonymize_row(headers: list[str], row: dict) -> dict:
    """Apply anonymization rules to a single row."""
    out = {}
    for col in headers:
        value = row.get(col, "")

        # Drop column entirely
        if col in DROP_COLUMNS or col in USER_CODE_COLUMNS:
            continue

        # Hash student identifiers
        if col in STUDENT_ID_COLUMNS:
            out[col] = hash_student_id(value)
            continue

        # Hash staff identifiers
        if col in STAFF_ID_COLUMNS:
            out[col] = hash_staff_id(value)
            continue

        # Null out free-text fields
        if col in NULL_TEXT_COLUMNS:
            out[col] = ""
            continue

        # Keep all other columns (analytical)
        out[col] = value

    return out


def anonymize_file(file_path: Path, output_path: Path) -> dict:
    """Anonymize a single CSV file. Returns metadata for manifest."""
    headers, rows = read_csv_rows(file_path)

    # Determine which columns we're keeping
    kept_cols = [h for h in headers if h not in DROP_COLUMNS and h not in USER_CODE_COLUMNS]
    dropped_cols = [h for h in headers if h in DROP_COLUMNS or h in USER_CODE_COLUMNS]
    hashed_student_cols = [h for h in headers if h in STUDENT_ID_COLUMNS]
    hashed_staff_cols = [h for h in headers if h in STAFF_ID_COLUMNS]
    nulled_cols = [h for h in headers if h in NULL_TEXT_COLUMNS]

    # Anonymize rows
    anon_rows = [anonymize_row(headers, row) for row in rows]

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try Parquet, fall back to CSV
    wrote_parquet = False
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        # Build arrow table from anonymized rows
        if anon_rows:
            table = pa.Table.from_pylist(anon_rows)
        else:
            # Empty table — create from schema
            table = pa.table({col: [] for col in kept_cols})

        pq.write_table(table, str(output_path.with_suffix(".parquet")))
        wrote_parquet = True
        actual_output = str(output_path.with_suffix(".parquet"))
    except ImportError:
        # Fall back to CSV
        with open(output_path.with_suffix(".csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=kept_cols, extrasaction="ignore")
            writer.writeheader()
            for row in anon_rows:
                writer.writerow(row)
        actual_output = str(output_path.with_suffix(".csv"))

    return {
        "source_file": str(file_path),
        "output_file": actual_output,
        "format": "parquet" if wrote_parquet else "csv",
        "rows_in": len(rows),
        "rows_out": len(anon_rows),
        "columns_in": len(headers),
        "columns_out": len(kept_cols),
        "dropped_columns": dropped_cols,
        "hashed_student_columns": hashed_student_cols,
        "hashed_staff_columns": hashed_staff_cols,
        "nulled_text_columns": nulled_cols,
    }


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    if not SOURCE_DIR.exists():
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

    # Find all source files
    source_files = list_source_files()
    if not source_files:
        print("ERROR: No source files found. Check path and permissions.")
        print("  If macOS TCC is blocking access, grant Full Disk Access to Terminal")
        print("  in System Settings > Privacy & Security > Full Disk Access.")
        sys.exit(1)

    total_files = sum(len(v) for v in source_files.values())
    print(f"Found {total_files} files across {len(source_files)} categories:")
    for cat, files in source_files.items():
        print(f"  {cat}: {len(files)} files")
    print()

    # Process each file
    manifest = {
        "anonymized_at": datetime.now().isoformat(),
        "source_dir": str(SOURCE_DIR),
        "output_dir": str(OUTPUT_DIR),
        "student_salt": STUDENT_SALT,
        "staff_salt": STAFF_SALT,
        "files": [],
        "summary": {
            "total_files": 0,
            "total_rows_in": 0,
            "total_rows_out": 0,
            "total_columns_dropped": 0,
            "total_student_ids_hashed": 0,
            "total_staff_ids_hashed": 0,
        }
    }

    for category, files in sorted(source_files.items()):
        print(f"Processing {category}/")
        for src_file in files:
            # Determine output path preserving subdirectory structure
            rel_path = src_file.relative_to(SOURCE_DIR)
            out_path = OUTPUT_DIR / rel_path.with_suffix("")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                meta = anonymize_file(src_file, out_path)
                manifest["files"].append(meta)
                manifest["summary"]["total_files"] += 1
                manifest["summary"]["total_rows_in"] += meta["rows_in"]
                manifest["summary"]["total_rows_out"] += meta["rows_out"]
                manifest["summary"]["total_columns_dropped"] += len(meta["dropped_columns"])
                manifest["summary"]["total_student_ids_hashed"] += len(meta["hashed_student_columns"])
                manifest["summary"]["total_staff_ids_hashed"] += len(meta["hashed_staff_columns"])
                print(f"  {src_file.name}: {meta['rows_in']}→{meta['rows_out']} rows, "
                      f"{meta['columns_in']}→{meta['columns_out']} cols ({meta['format']})")
            except Exception as e:
                print(f"  ERROR {src_file.name}: {e}")
                manifest["files"].append({
                    "source_file": str(src_file),
                    "error": str(e),
                })

    # Write manifest
    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone: {manifest['summary']['total_files']} files, "
          f"{manifest['summary']['total_rows_in']}→{manifest['summary']['total_rows_out']} rows")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()