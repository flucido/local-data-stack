#!/usr/bin/env python3
"""
anonymize_aeries.py — Strip PII from Aeries SIS test data and output anonymized files.

Reads from: ~/Desktop/AeRIES test data/  (source — contains real student PII)
Writes to:  data/aeries_anonymized/     (output — safe for warehouse loading)

Anonymization rules (per AERIES_DATA_INVENTORY.md):
  1. Hash StudentID (and all student identifiers) with HMAC-SHA256 + env salt
  2. Hash staff IDs with a separate env salt
  3. Drop name, DOB, address, phone, email, login fields entirely
  4. NULL out free-text fields (Comment, ShortDescription, Initials, etc.)
  5. Drop unknown UserCode fields
  6. Strip whitespace on all fields (critical for 2022-23 file)
  7. Preserve all analytical columns

Uses _transformed/ files where available (already flattened from raw JSON).
Outputs Parquet if pyarrow is available, falling back to CSV.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────

SOURCE_DIR = Path.home() / "Desktop" / "AeRIES test data"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "aeries_anonymized"
STREAM_BATCH_SIZE = 5000


def _require_env_salt(var_name: str) -> str:
    """Fetch a required HMAC salt from the environment and enforce >=16 chars."""
    if var_name not in os.environ:
        raise ValueError(f"Required environment variable {var_name} is unset")
    salt = os.environ[var_name]
    if len(salt) < 16:
        raise ValueError(f"{var_name} must be at least 16 characters long")
    return salt


def get_salts() -> tuple[str, str]:
    """Validate and return (student_salt, staff_salt) from environment."""
    return _require_env_salt("LFED_STUDENT_SALT"), _require_env_salt("LFED_STAFF_SALT")


# ── Column classification ──────────────────────────────────────────────

STUDENT_ID_COLUMNS = {
    "StudentID",
    "Admin_StudentID",
    "OldStudentID",
    "StateStudentID",
    "StudentNumber",
}

STAFF_ID_COLUMNS = {
    "CounselorNumber",
    "HomeRoomTeacherNumber",
    "ElementaryTeacherNumber",
    "TeacherNumber",
    "MP_PrimaryStaffID",
}

DROP_COLUMNS = {
    # Names
    "LastName",
    "FirstName",
    "MiddleName",
    "LastNameAlias",
    "FirstNameAlias",
    "MiddleNameAlias",
    "NameSuffix",
    "ParentGuardianName",
    "ElementaryTeacherName",
    # DOB
    "Birthdate",
    # Addresses
    "MailingAddress",
    "MailingAddressCity",
    "MailingAddressState",
    "MailingAddressZipCode",
    "MailingAddressZipExt",
    "ResidenceAddress",
    "ResidenceAddressCity",
    "ResidenceAddressState",
    "ResidenceAddressZipCode",
    "ResidenceAddressZipExt",
    # Phones
    "HomePhone",
    "StudentMobilePhone",
    # Emails
    "StudentPersonalEmailAddress",
    "ParentEmailAddress",
    "StudentEmailAddress",
    # Login
    "NetworkLoginID",
    # Quasi-PII
    "LockerNumber",
    "FamilyKey",
}

NULL_TEXT_COLUMNS = {
    "Comment",
    "ShortDescription",
    "ReferredByOther",
    "Initials",
    "MP_Comment1Code",
    "MP_Comment2Code",
    "MP_Comment3Code",
}

USER_CODE_COLUMNS = {f"UserCode{i}" for i in range(1, 14)}

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


@functools.lru_cache(maxsize=65536)
def _hmac_sha256(salt: str, clean_value: str) -> str:
    """Cached full-length HMAC-SHA256 digest per unique identifier."""
    return hmac.new(salt.encode("utf-8"), clean_value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_student_id(value: str) -> str:
    """HMAC-SHA256 hash of student ID with LFED_STUDENT_SALT."""
    salt = _require_env_salt("LFED_STUDENT_SALT")
    if not value or not value.strip():
        return ""
    return _hmac_sha256(salt, value.strip())


def hash_staff_id(value: str) -> str:
    """HMAC-SHA256 hash of staff ID with LFED_STAFF_SALT."""
    salt = _require_env_salt("LFED_STAFF_SALT")
    if not value or not value.strip():
        return ""
    return _hmac_sha256(salt, value.strip())


# ── File discovery (works around macOS TCC on ~/Desktop) ──────────────

_LIST_APPLESCRIPT = """
on run argv
    set targetFolder to POSIX file (item 1 of argv) as alias
    tell application "System Events"
        try
            set fileList to name of every file of targetFolder
            set AppleScript's text item delimiters to linefeed
            return fileList as text
        on error
            return ""
        end try
    end tell
end run
"""

_READ_APPLESCRIPT = """
on run argv
    set filePath to POSIX file (item 1 of argv)
    try
        return read filePath as «class utf8»
    on error
        return read filePath
    end try
end run
"""


def list_source_files() -> dict[str, list[Path]]:
    """Find all source CSV files, grouped by output category."""
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

        matched = _list_via_applescript(subdir, pattern)
        if matched:
            files[category] = matched

    return files


def _list_via_applescript(directory: Path, pattern: str) -> list[Path]:
    """List files in a TCC-restricted directory via parameterized AppleScript."""
    try:
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        regex = re.compile(f"^{regex_pattern}$")

        proc = subprocess.run(
            ["osascript", "-e", _LIST_APPLESCRIPT, str(directory)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        names = [n.strip() for n in proc.stdout.strip().split("\n") if n.strip()]
        return sorted(directory / name for name in names if regex.match(name))
    except Exception:
        return []


def _strip_row(row: dict) -> dict[str, str]:
    stripped: dict[str, str] = {}
    for k, v in row.items():
        key = k.strip() if isinstance(k, str) else str(k or "")
        val = v.strip() if isinstance(v, str) else str(v or "")
        stripped[key] = val
    return stripped


def iter_csv_rows(file_path: Path) -> tuple[list[str], Iterator[dict[str, str]]]:
    """Stream a CSV file returning (headers, generator of stripped row dicts)."""
    try:
        fh = open(file_path, encoding="utf-8", errors="replace", newline="")
    except PermissionError:
        proc = subprocess.run(
            ["osascript", "-e", _READ_APPLESCRIPT, str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        reader = csv.DictReader(io.StringIO(proc.stdout))
        headers = [h.strip() for h in reader.fieldnames or []]

        def _gen_from_mem() -> Iterator[dict[str, str]]:
            for row in reader:
                yield _strip_row(row)

        return headers, _gen_from_mem()

    reader = csv.DictReader(fh)
    headers = [h.strip() for h in reader.fieldnames or []]

    def _gen_from_file() -> Iterator[dict[str, str]]:
        try:
            for row in reader:
                yield _strip_row(row)
        finally:
            fh.close()

    return headers, _gen_from_file()


def read_csv_rows(file_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Compatibility wrapper over iter_csv_rows."""
    headers, row_iter = iter_csv_rows(file_path)
    return headers, list(row_iter)


# ── Anonymization ─────────────────────────────────────────────────────


def anonymize_row(headers: list[str], row: dict) -> dict[str, str]:
    """Apply anonymization rules to a single row."""
    out: dict[str, str] = {}
    for col in headers:
        value = row.get(col, "")

        if col in DROP_COLUMNS or col in USER_CODE_COLUMNS:
            continue
        if col in STUDENT_ID_COLUMNS:
            out[col] = hash_student_id(value)
            continue
        if col in STAFF_ID_COLUMNS:
            out[col] = hash_staff_id(value)
            continue
        if col in NULL_TEXT_COLUMNS:
            out[col] = ""
            continue
        out[col] = value

    return out


def anonymize_file(file_path: Path, output_path: Path) -> dict:
    """Stream-anonymize a single CSV file. Returns metadata for manifest."""
    get_salts()
    headers, row_iter = iter_csv_rows(file_path)

    kept_cols = [h for h in headers if h not in DROP_COLUMNS and h not in USER_CODE_COLUMNS]
    dropped_cols = [h for h in headers if h in DROP_COLUMNS or h in USER_CODE_COLUMNS]
    hashed_student_cols = [h for h in headers if h in STUDENT_ID_COLUMNS]
    hashed_staff_cols = [h for h in headers if h in STAFF_ID_COLUMNS]
    nulled_cols = [h for h in headers if h in NULL_TEXT_COLUMNS]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_in = 0
    rows_out = 0
    wrote_parquet = False

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        parquet_path = output_path.with_suffix(".parquet")
        schema = pa.schema([(col, pa.string()) for col in kept_cols])
        batch: list[dict[str, str]] = []
        with pq.ParquetWriter(str(parquet_path), schema) as writer:
            for row in row_iter:
                rows_in += 1
                batch.append(anonymize_row(headers, row))
                rows_out += 1
                if len(batch) >= STREAM_BATCH_SIZE:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch.clear()
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch.clear()
            elif rows_out == 0:
                writer.write_table(
                    pa.table({col: pa.array([], type=pa.string()) for col in kept_cols})
                )
        wrote_parquet = True
        actual_output = str(parquet_path)
    except ImportError:
        csv_path = output_path.with_suffix(".csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=kept_cols, extrasaction="ignore")
            writer.writeheader()
            for row in row_iter:
                rows_in += 1
                writer.writerow(anonymize_row(headers, row))
                rows_out += 1
        actual_output = str(csv_path)

    return {
        "source_file": str(file_path),
        "output_file": actual_output,
        "format": "parquet" if wrote_parquet else "csv",
        "rows_in": rows_in,
        "rows_out": rows_out,
        "columns_in": len(headers),
        "columns_out": len(kept_cols),
        "dropped_columns": dropped_cols,
        "hashed_student_columns": hashed_student_cols,
        "hashed_staff_columns": hashed_staff_cols,
        "nulled_text_columns": nulled_cols,
    }


def build_manifest(source_dir: Path, output_dir: Path) -> dict:
    """Create the base manifest dictionary without exposing HMAC salts."""
    return {
        "anonymized_at": datetime.now().isoformat(),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "files": [],
        "summary": {
            "total_files": 0,
            "total_rows_in": 0,
            "total_rows_out": 0,
            "total_columns_dropped": 0,
            "total_student_ids_hashed": 0,
            "total_staff_ids_hashed": 0,
        },
    }


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    get_salts()
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    if not SOURCE_DIR.exists():
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

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

    manifest = build_manifest(SOURCE_DIR, OUTPUT_DIR)

    for category, files in sorted(source_files.items()):
        print(f"Processing {category}/")
        for src_file in files:
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
                manifest["summary"]["total_student_ids_hashed"] += len(
                    meta["hashed_student_columns"]
                )
                manifest["summary"]["total_staff_ids_hashed"] += len(meta["hashed_staff_columns"])
                print(
                    f"  {src_file.name}: {meta['rows_in']}→{meta['rows_out']} rows, "
                    f"{meta['columns_in']}→{meta['columns_out']} cols ({meta['format']})"
                )
            except Exception as e:
                print(f"  ERROR {src_file.name}: {e}")
                manifest["files"].append(
                    {
                        "source_file": str(src_file),
                        "error": str(e),
                    }
                )

    manifest_path = OUTPUT_DIR / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"\nDone: {manifest['summary']['total_files']} files, "
        f"{manifest['summary']['total_rows_in']}→{manifest['summary']['total_rows_out']} rows"
    )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
