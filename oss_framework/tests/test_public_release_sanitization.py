from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_private_artifacts_removed_from_filesystem() -> None:
    # Real private source drops must never be present in the working tree.
    for relative_path in [
        "AeriesTestData2_2026",
        "AeriesTestData2_2026-20260228T034417Z-3-001.zip",
    ]:
        assert not (REPO_ROOT / relative_path).exists()


def test_local_warehouse_is_gitignored() -> None:
    # analytics.duckdb is the live local dev warehouse (and the NL->SQL test
    # fixture). It legitimately exists on dev machines, so the release gate
    # is that git can never track it — not that it is absent from disk.
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert "oss_framework/data/" in gitignore


def test_public_config_uses_generic_environment_driven_paths() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text()
    assert "projects/local-data-stack" not in env_example
    assert "replace_with_your_aeries_api_key" in env_example
    assert "RILL_DUCKDB_DSN=../oss_framework/data/analytics.duckdb" in env_example

    dbt_project = (REPO_ROOT / "oss_framework/dbt/dbt_project.yml").read_text()
    assert "env_var('PII_SALT')" in dbt_project
    assert "'oea_2026'" not in dbt_project

    dbt_profiles = (REPO_ROOT / "oss_framework/dbt/profiles.yml").read_text()
    assert "env_var('DUCKDB_DATABASE_PATH'" in dbt_profiles

    # rill_project/connectors/duckdb.yaml was retired in 0951db6; rillv1 now
    # uses olap_connector in rill.yaml with env-driven DSN from .env.
    rill_yaml = (REPO_ROOT / "rill_project" / "rill.yaml").read_text()
    assert "olap_connector: duckdb" in rill_yaml
    assert not (REPO_ROOT / "rill_project" / "connectors" / "duckdb.yaml").exists()


def test_synthetic_sample_data_has_expected_shape() -> None:
    sample_path = REPO_ROOT / "oss_framework/data/sample_data/synthetic_student_metrics.parquet"
    table = pq.read_table(sample_path)

    assert table.num_rows == 5
    assert {
        "student_id",
        "student_alias",
        "academic_year",
        "school_id",
        "grade_level",
        "race_ethnicity",
        "ell_status",
        "special_education_status",
        "frl_status",
        "attendance_rate",
        "gpa",
        "discipline_incidents",
    }.issubset(set(table.column_names))
    assert all(
        student_id.startswith("SYN") for student_id in table.column("student_id").to_pylist()
    )


def test_dbt_pii_hashing_unification_and_no_hardcoded_salts() -> None:
    for rel in [
        "oss_framework/dbt/macros/hash_pii_secure.sql",
        "oss_framework/dbt/macros/hash_pii.sql",
        "oss_framework/dbt/STAGE2B_PRIVACY_DESIGN.md",
        "oss_framework/dbt/models/mart_features/features/fct_chronic_absence_features.sql",
        "oss_framework/dbt/models/mart_analytics/aggregations/agg_attendance_windows.sql",
    ]:
        text = (REPO_ROOT / rel).read_text()
        assert "oea_2026" not in text, f"Found hardcoded salt oea_2026 in {rel}"

    hash_pii_text = (REPO_ROOT / "oss_framework/dbt/macros/hash_pii.sql").read_text()
    assert "hash_pii_secure(" in hash_pii_text

    chronic_text = (
        REPO_ROOT
        / "oss_framework/dbt/models/mart_features/features/fct_chronic_absence_features.sql"
    ).read_text()
    assert chronic_text.count("hash_pii_secure('ra.student_id')") == 3

    windows_text = (
        REPO_ROOT
        / "oss_framework/dbt/models/mart_analytics/aggregations/agg_attendance_windows.sql"
    ).read_text()
    assert "hash_pii_secure('ra.student_id')" in windows_text

    fact_enrollment = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/fact_enrollment.sql"
    ).read_text()
    assert "['se.student_id_raw'" not in fact_enrollment.splitlines()[13]
    assert "[hash_pii_secure('se.student_id_raw')" in fact_enrollment.splitlines()[13]

    fact_academics = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/fact_academic_records.sql"
    ).read_text()
    assert "['sar.student_id_raw'" not in fact_academics.splitlines()[13]
    assert "[hash_pii_secure('sar.student_id_raw')" in fact_academics.splitlines()[13]


def test_no_hardcoded_salts_in_dbt_models_or_scripts() -> None:
    forbidden = (
        "oea_2026",
        "aeries_student_2026_salt_v1",
        "aeries_staff_2026_salt_v1",
    )
    scan_roots = [
        REPO_ROOT / "oss_framework" / "dbt" / "models",
        REPO_ROOT / "scripts",
    ]
    for root in scan_roots:
        for path in root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                assert token not in content, f"Forbidden salt {token!r} found in {path}"


def test_anonymize_aeries_security_and_streaming(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import hmac
    import subprocess
    from unittest.mock import MagicMock

    import scripts.anonymize_aeries as anon

    student_salt = "unit_test_student_hmac_salt_2026"
    staff_salt = "unit_test_staff_hmac_salt_2026_v2"
    monkeypatch.setenv("LFED_STUDENT_SALT", student_salt)
    monkeypatch.setenv("LFED_STAFF_SALT", staff_salt)

    expected = hmac.new(student_salt.encode(), b"998877", hashlib.sha256).hexdigest()
    digest = anon.hash_student_id(" 998877 ")
    assert len(digest) == 64
    assert digest == expected

    # Missing or short salt must fail fast
    monkeypatch.setenv("LFED_STUDENT_SALT", "too_short")
    try:
        anon.hash_student_id("998877")
        raise AssertionError("Expected ValueError for short LFED_STUDENT_SALT")
    except ValueError:
        pass
    monkeypatch.setenv("LFED_STUDENT_SALT", student_salt)

    # Manifest must never include student_salt or staff_salt
    manifest = anon.build_manifest(tmp_path / "src", tmp_path / "out")
    assert "student_salt" not in manifest
    assert "staff_salt" not in manifest

    # Streaming CSV anonymization check
    src_csv = tmp_path / "students_2025.csv"
    src_csv.write_text(
        "StudentID,FirstName,LastName,Grade,Comment\n"
        " 998877 ,Alice,Smith,8,Private note\n"
        "998878,Bob,Jones,8,Another note\n",
        encoding="utf-8",
    )
    out_base = tmp_path / "out" / "students_2025"
    meta = anon.anonymize_file(src_csv, out_base)
    assert meta["rows_in"] == 2
    assert meta["rows_out"] == 2
    assert set(meta["dropped_columns"]) == {"FirstName", "LastName"}

    # Parameterized AppleScript argv check (no path interpolation)
    evil_dir = tmp_path / 'evil" & do shell script "id" & "'
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        m = MagicMock()
        m.stdout = ""
        return m

    monkeypatch.setattr(subprocess, "run", fake_run)
    anon._list_via_applescript(evil_dir, "students_*.csv")
    assert len(calls) == 1
    assert calls[0][:2] == ["osascript", "-e"]
    assert calls[0][3] == str(evil_dir)
    assert str(evil_dir) not in calls[0][2]
    assert "on run argv" in calls[0][2]
    assert "POSIX file (item 1 of argv)" in calls[0][2]


def test_k_anonymity_suppression_across_marts_and_exports() -> None:
    rill_export = (
        REPO_ROOT / "oss_framework/dbt/models/exports/rill_chronic_absenteeism.sql"
    ).read_text()
    assert "SELECT * FROM" not in rill_export
    assert "HAVING COUNT(*) >= 5" in rill_export

    hex_model = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/analytics_for_hex.sql"
    ).read_text()
    assert "schema='features'" in hex_model
    assert "materialized='view'" in hex_model

    cohort_models = [
        "oss_framework/dbt/models/mart_analytics/analytics/v_equity_outcomes_by_demographics.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/math_8_cohort_tracking.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/algebra_1_outcomes.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/lead_program_enrollment.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/math_pathways_7th_grade.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/equity_by_race.sql",
    ]
    for rel in cohort_models:
        sql = (REPO_ROOT / rel).read_text()
        assert "HAVING COUNT(" in sql and ">= 5" in sql, f"Missing HAVING k>=5 suppression in {rel}"

    equity_race = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/equity_by_race.sql"
    ).read_text()
    assert "WHEN SUM(CASE WHEN homeless_flag THEN 1 ELSE 0 END) >= 5" in equity_race
    assert "WHEN SUM(CASE WHEN special_education_flag THEN 1 ELSE 0 END) >= 5" in equity_race

    class_eff = (
        REPO_ROOT
        / "oss_framework/dbt/models/mart_analytics/aggregations/fact_class_effectiveness.sql"
    ).read_text()
    assert "WHEN SUM(CASE WHEN english_learner THEN 1 ELSE 0 END) >= 5" in class_eff
    assert "WHEN SUM(CASE WHEN special_education THEN 1 ELSE 0 END) >= 5" in class_eff
    assert "WHEN SUM(CASE WHEN free_reduced_lunch THEN 1 ELSE 0 END) >= 5" in class_eff

    models_yml = REPO_ROOT / "oss_framework/dbt/models/mart_analytics/_analytics__models.yml"
    assert models_yml.exists()
    yml_text = models_yml.read_text()
    assert "test_k_anonymity" in yml_text
    assert "min_k: 5" in yml_text
