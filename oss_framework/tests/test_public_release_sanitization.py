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
    assert "hash_pii_secure('ra.student_id')" in chronic_text

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


def test_schema_contract_alignment_across_dbt_and_prompts() -> None:
    school_summary = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/school_summary.sql"
    ).read_text()
    for required in (
        "academic_year",
        "school_name",
        "total_students",
        "student_count",
        "avg_attendance_rate",
        "avg_gpa",
    ):
        assert required in school_summary, f"Missing {required} in school_summary.sql"
    assert "dim_schools" in school_summary

    equity_by_race = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/equity_by_race.sql"
    ).read_text()
    for required in (
        "academic_year",
        "primary_race",
        "is_multi_racial",
        "incident_count",
        "avg_discipline_incidents",
    ):
        assert required in equity_by_race, f"Missing {required} in equity_by_race.sql"

    prompts_text = (REPO_ROOT / "nl_query/prompts.py").read_text()
    assert "SED=Socioeconomically Disadvantaged" in prompts_text


def test_attendance_rate_scale_normalization_in_hex_models() -> None:
    hex_sql = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/analytics_for_hex.sql"
    ).read_text()
    assert (
        "WHEN COALESCE(a.attendance_rate, 0) <= 1.0 THEN ROUND(COALESCE(a.attendance_rate, 0) * 100.0, 2)"
        in hex_sql
    )


def test_staging_and_mart_constants_windows_and_multiyear_joins() -> None:
    stg_students = (
        REPO_ROOT / "oss_framework/dbt/models/staging/aeries/stg_aeries__students.sql"
    ).read_text()
    assert "'2024-2025' as academic_year" not in stg_students
    assert "false as ell_program_flag" not in stg_students
    assert "COALESCE(TRY_CAST(s.ell_status AS BOOLEAN), FALSE)" in stg_students
    assert "CAST(NULL AS VARCHAR) as race_code_1" not in stg_students

    for rel in (
        "oss_framework/dbt/models/staging/aeries/stg_aeries__attendance.sql",
        "oss_framework/dbt/models/staging/aeries/stg_aeries__discipline.sql",
    ):
        assert "'2024-2025' as academic_year" not in (REPO_ROOT / rel).read_text()

    fact_disc = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/fact_discipline.sql"
    ).read_text()
    assert "COALESCE(sd.incident_type, sd.short_description)" in fact_disc
    assert "COALESCE(sd.resolution, sd.disposition_code)" in fact_disc

    agg_disc = (
        REPO_ROOT
        / "oss_framework/dbt/models/mart_analytics/aggregations/agg_discipline_windows.sql"
    ).read_text()
    assert "CURRENT_DATE" not in agg_disc
    assert "MAX(DATE(incident_date))" in agg_disc or "MAX(incident_date)" in agg_disc

    fct_acad = (
        REPO_ROOT / "oss_framework/dbt/models/mart_features/features/fct_academic_features.sql"
    ).read_text()
    assert "CURRENT_DATE" not in fct_acad
    assert "MAX(created_at)" in fct_acad

    caspp = (
        REPO_ROOT / "oss_framework/dbt/models/staging/cde/stg_cde__assessment_caspp.sql"
    ).read_text()
    assert "students_with_scores" in caspp
    assert "AVG(mean_scale_score) as mean_scale_score" not in caspp

    ca_stg = (
        REPO_ROOT / "oss_framework/dbt/models/staging/cde/stg_cde__chronic_absenteeism.sql"
    ).read_text()
    assert "IS NULL" in ca_stg

    susp_stg = (
        REPO_ROOT / "oss_framework/dbt/models/staging/cde/stg_cde__suspension.sql"
    ).read_text()
    assert "IS NULL" in susp_stg

    dim_students = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/dim_students.sql"
    ).read_text()
    assert "unique_key=['student_id_hash', 'academic_year']" in dim_students

    for rel in (
        "oss_framework/dbt/models/mart_analytics/analytics/v_chronic_absenteeism_risk.sql",
        "oss_framework/dbt/models/mart_analytics/analytics/v_wellbeing_risk_profiles.sql",
        "oss_framework/dbt/models/mart_analytics/analytics/v_equity_outcomes_by_demographics.sql",
        "oss_framework/dbt/models/mart_features/features/fct_academic_features.sql",
        "oss_framework/dbt/models/mart_analytics/aggregations/fact_class_effectiveness.sql",
    ):
        text = (REPO_ROOT / rel).read_text()
        assert ".academic_year =" in text, f"Missing multi-year join in {rel}"

    mapping_sql = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/dim_school_cds_mapping.sql"
    ).read_text()
    assert "LEFT(i.cleaned_name, 1) = LEFT(c.cleaned_name, 1)" in mapping_sql

    dim_schools = (
        REPO_ROOT / "oss_framework/dbt/models/mart_core/core/dim_schools.sql"
    ).read_text()
    assert "COALESCE(m.cde_school_name, 'SCHOOL_' || s.school_id) AS school_name" in dim_schools


def test_ci_workflow_packaging_and_benchmark_schema_contracts() -> None:
    workflow = (REPO_ROOT / ".github/workflows/test.yml").read_text()
    assert "paths:" not in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "|| true" not in workflow
    for job_name in (
        "python-lint-and-test:",
        "desktop-ui-test:",
        "desktop-rust-test:",
        "dbt-smoke-test:",
    ):
        assert job_name in workflow, f"Missing CI job {job_name}"

    cargo_toml = (REPO_ROOT / "desktop/Cargo.toml").read_text()
    assert 'default = ["bundled-duckdb"]' in cargo_toml

    build_rs = (REPO_ROOT / "desktop/build.rs").read_text()
    assert 'cfg!(target_os = "macos")' in build_rs

    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    assert '"nl_query*"' in pyproject
    assert '"scripts*"' in pyproject
    assert '"training*"' in pyproject
    assert (
        "--cov=oss_framework"
        not in pyproject.split("[tool.pytest.ini_options]")[1].split("[tool.coverage")[0]
    )

    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert "*.duckdb.building" in gitignore
    assert "*_building.duckdb" in gitignore

    for perf_rel in (
        "scripts/performance/benchmark.py",
        "scripts/performance/duckdb_indexes.sql",
    ):
        perf_text = (REPO_ROOT / perf_rel).read_text()
        assert "fact_grades" not in perf_text
        assert "fact_discipline_incidents" not in perf_text
        assert "score_chronic_absenteeism_risk" not in perf_text
        assert "student_id_hash" in perf_text


def test_phase4_t1_stage1_and_staging_pii_minimization(tmp_path: Path, monkeypatch) -> None:
    import polars as pl

    # 1. HTTPS enforcement on AeriesConnector unless LFED_ALLOW_INSECURE_HTTP=1
    import pytest

    from oss_framework.connectors.aeries import AeriesConnector
    from oss_framework.pipelines.aeries_dlt_pipeline import filter_student_record
    from oss_framework.pipelines.aeries_to_parquet import AeriesToParquetPipeline

    monkeypatch.delenv("LFED_ALLOW_INSECURE_HTTP", raising=False)
    with pytest.raises(ValueError, match="https://"):
        AeriesConnector(
            base_url="http://insecure.district.local/v5", api_key="secret_cert", test_mode=False
        )

    monkeypatch.setenv("LFED_ALLOW_INSECURE_HTTP", "1")
    insecure_ok = AeriesConnector(
        base_url="http://localhost:8080/v5", api_key="secret_cert", test_mode=False
    )
    assert insecure_ok.base_url.startswith("http://")
    monkeypatch.delenv("LFED_ALLOW_INSECURE_HTTP", raising=False)

    # 2. Student allowlist filtering drops phones, addresses, StateStudentID, OldStudentID
    raw_rec = {
        "student_id": "1001",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "HomePhone": "555-0100",
        "StudentMobilePhone": "555-0199",
        "MailingAddress": "123 Main St",
        "MailingAddressZipCode": "90210",
        "ResidenceAddress": "123 Main St",
        "StateStudentID": "SSID999",
        "OldStudentID": "OLD1",
    }
    filtered = filter_student_record(raw_rec)
    assert "student_id" in filtered
    for dropped in (
        "HomePhone",
        "StudentMobilePhone",
        "MailingAddress",
        "MailingAddressZipCode",
        "ResidenceAddress",
        "StateStudentID",
        "OldStudentID",
    ):
        assert dropped not in filtered

    # Verify Polars CSV->Parquet pipeline also strips disallowed student columns
    src_dir = tmp_path / "src" / "students"
    src_dir.mkdir(parents=True)
    csv_file = src_dir / "students_2024_2025.csv"
    csv_file.write_text(
        "StudentID,FirstName,Grade,SchoolCode,HomePhone,StudentMobilePhone,MailingAddress,ResidenceAddress,StateStudentID,OldStudentID\n"
        "1001,Ada,8,1,555-0100,555-0199,123 Main,123 Main,SSID999,OLD1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("oss_framework.pipelines.aeries_to_parquet.SOURCE_BASE", tmp_path / "src")
    monkeypatch.setattr("oss_framework.pipelines.aeries_to_parquet.TARGET_BASE", tmp_path / "out")
    res = AeriesToParquetPipeline().convert("students", "2024-2025")
    assert res["success"] is True
    out_df = pl.read_parquet(tmp_path / "out" / "students" / "year=2024-2025" / "part-000.parquet")
    assert "StudentID" in out_df.columns
    for dropped in (
        "HomePhone",
        "StudentMobilePhone",
        "MailingAddress",
        "ResidenceAddress",
        "StateStudentID",
        "OldStudentID",
    ):
        assert dropped not in out_df.columns

    # 3. Post-hook on priv_pii_lookup_table drops plaintext PII from stg_aeries__students
    lookup_sql = (
        REPO_ROOT / "oss_framework/dbt/models/mart_privacy/privacy/priv_pii_lookup_table.sql"
    ).read_text()
    assert "DROP COLUMN IF EXISTS first_name_raw" in lookup_sql
    assert "DROP COLUMN IF EXISTS last_name_raw" in lookup_sql
    assert "DROP COLUMN IF EXISTS date_of_birth_raw" in lookup_sql

    # 4. Masked names removed from priv_student_hashes
    hashes_sql = (
        REPO_ROOT / "oss_framework/dbt/models/mart_privacy/privacy/priv_student_hashes.sql"
    ).read_text()
    assert "first_name_masked" not in hashes_sql
    assert "last_name_masked" not in hashes_sql

    # 5. Admin names and phone removed from stg_cde__schools
    cde_schools_sql = (
        REPO_ROOT / "oss_framework/dbt/models/staging/cde/stg_cde__schools.sql"
    ).read_text()
    assert "admin_first_name" not in cde_schools_sql
    assert "admin_last_name" not in cde_schools_sql
    assert "phone_number" not in cde_schools_sql


def test_phase4_t2_scrypt_kdf_break_glass_decrypt_and_retention(monkeypatch, caplog) -> None:
    import logging
    import sys

    import duckdb
    import pytest

    sys.path.insert(0, str(REPO_ROOT / "oss_framework" / "dbt" / "udfs"))
    import pii_crypto
    import pii_crypto_plugin

    from oss_framework.scripts import config as oss_config

    # 1. Weak / placeholder encryption keys rejected; scrypt round-trip + audit log
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "too_short_key")
    with pytest.raises((ValueError, RuntimeError)):
        pii_crypto.aes_encrypt_pii("Alice")

    monkeypatch.setenv("PII_ENCRYPTION_KEY", "replace_with_your_secure_random_salt")
    with pytest.raises((ValueError, RuntimeError)):
        pii_crypto.aes_encrypt_pii("Alice")

    monkeypatch.setenv(
        "PII_ENCRYPTION_KEY",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    token = pii_crypto.aes_encrypt_pii("Alice")
    with caplog.at_level(logging.WARNING):
        plain = pii_crypto.aes_decrypt_pii(token)
    assert plain == "Alice"
    assert any("PII_DECRYPT_AUDIT" in rec.message for rec in caplog.records)

    # 2. Break-glass registration of aes_decrypt_pii
    plugin = pii_crypto_plugin.Plugin(name="pii_crypto_plugin", plugin_config={})
    con1 = duckdb.connect(":memory:")
    monkeypatch.delenv("LFED_ENABLE_PII_DECRYPT", raising=False)
    plugin.configure_connection(con1)
    enc_val = con1.execute("SELECT aes_encrypt_pii('Bob')").fetchone()[0]
    with pytest.raises(duckdb.Error):
        con1.execute("SELECT aes_decrypt_pii(?)", [enc_val])
    con1.close()

    con2 = duckdb.connect(":memory:")
    monkeypatch.setenv("LFED_ENABLE_PII_DECRYPT", "1")
    plugin.configure_connection(con2)
    assert con2.execute("SELECT aes_decrypt_pii(?)", [enc_val]).fetchone()[0] == "Bob"
    con2.close()
    monkeypatch.delenv("LFED_ENABLE_PII_DECRYPT", raising=False)

    # 3. Config validation for PII_SALT and retention purge helper
    monkeypatch.setenv("PII_SALT", "replace_with_your_secure_random_salt")
    with pytest.raises(ValueError, match="PII_SALT"):
        oss_config.validate_config(require_aeries=False)

    monkeypatch.setenv("PII_SALT", "short")
    with pytest.raises(ValueError, match="PII_SALT"):
        oss_config.validate_config(require_aeries=False)

    monkeypatch.setenv("PII_SALT", "test_32_byte_random_hmac_salt_value_2026")
    assert oss_config.validate_config(require_aeries=False) is True

    ret_con = duckdb.connect(":memory:")
    ret_con.execute(
        "CREATE TABLE main_students (student_id_hash VARCHAR, withdrawal_date DATE); "
        "INSERT INTO main_students VALUES ('old_stu', DATE '2015-06-01'), ('active_stu', NULL), ('recent_stu', CURRENT_DATE - INTERVAL '1 year');"
    )
    purged = oss_config.purge_expired_records(ret_con, retention_years=5)
    assert purged >= 1
    remaining = [
        r[0]
        for r in ret_con.execute("SELECT student_id_hash FROM main_students ORDER BY 1").fetchall()
    ]
    assert remaining == ["active_stu", "recent_stu"]
    ret_con.close()

    # 4. SECURITY.md truthfulness check
    sec_md = (REPO_ROOT / "SECURITY.md").read_text()
    assert "PRIVACY_SALT" not in sec_md
    for var_name in ("PII_SALT", "PII_ENCRYPTION_KEY", "DATA_RETENTION_YEARS"):
        assert var_name in sec_md


def test_phase5_t3_streaming_cde_zip_and_single_pass_parquet_exports(tmp_path: Path) -> None:
    import zipfile

    import duckdb

    from oss_framework.pipelines.cde_data_pipeline import CDEDataLoader
    from scripts.export_to_rill import export_view_to_parquet

    # 1. CDE zip domain streams via zf.open + sink_parquet + collect(engine="streaming")
    raw_dir = tmp_path / "cde_raw"
    raw_dir.mkdir()
    sbac_zip = raw_dir / "sb_ca2024_all_csv_v1.zip"
    with zipfile.ZipFile(sbac_zip, "w") as zf:
        zf.writestr(
            "sb_ca2024_all_csv_v1.txt",
            "County_Code^District_Code^School_Code^Test_Year^Mean_Scale_Score\n"
            "19^64733^0000001^2024^2540.5\n"
            "19^64733^0000002^2024^*\n",
        )

    loader = CDEDataLoader(data_dir=str(raw_dir))
    rows = list(loader.load_sbac_caaspp())
    assert len(rows) == 2
    assert rows[0]["Mean_Scale_Score"] == "2540.5"
    assert rows[1]["Mean_Scale_Score"] is None  # '*' cleaned to None

    cde_src = (REPO_ROOT / "oss_framework/pipelines/cde_data_pipeline.py").read_text()
    assert "zf.read(" not in cde_src
    assert "sink_parquet" in cde_src

    # 2. aeries_to_parquet writes once without pre-counting CSV rows
    a2p_src = (REPO_ROOT / "oss_framework/pipelines/aeries_to_parquet.py").read_text()
    assert "rows_read = lf.select(pl.len()).collect().item()" not in a2p_src

    # 3. export_to_rill reads row_count from parquet_metadata instead of pre-running SELECT COUNT(*)
    rill_src = (REPO_ROOT / "scripts/export_to_rill.py").read_text()
    assert "parquet_metadata" in rill_src

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA main_analytics")
    con.execute(
        "CREATE VIEW main_analytics.test_rill_v AS SELECT 1 AS id, 'A' AS label UNION ALL SELECT 2, 'B'"
    )
    out_pq = tmp_path / "rill_out.parquet"
    res = export_view_to_parquet(con, "main_analytics.test_rill_v", out_pq, dry_run=False)
    assert res["status"] == "success"
    assert res["row_count"] == 2
    assert out_pq.exists()
    con.close()


def test_phase7_t2_macos_schedule_portability_and_css_contrast() -> None:
    sched = (REPO_ROOT / "scripts/schedule_pipeline.sh").read_text()
    assert ".env.template" not in sched
    assert ".env.example" in sched
    assert "gtimeout" in sched
    assert "subprocess.run" in sched

    css = (REPO_ROOT / "desktop/ui/src/styles.css").read_text()
    assert "#fca5a5" in css
    assert ":focus-visible" in css
    assert "contain-intrinsic-size: auto 320px auto 260px" not in css
    assert "contain-intrinsic-size: auto 320px;" in css


def test_final_review_dbt_multiyear_hex_and_chronic_joins() -> None:
    for rel in (
        "oss_framework/dbt/models/mart_analytics/hex_ready/math_8_cohort_tracking.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/algebra_1_outcomes.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/lead_program_enrollment.sql",
        "oss_framework/dbt/models/mart_analytics/hex_ready/math_pathways_7th_grade.sql",
    ):
        sql = (REPO_ROOT / rel).read_text()
        assert "ar.school_year = d.academic_year" in sql, f"Missing multi-year join in {rel}"

    m8 = (
        REPO_ROOT / "oss_framework/dbt/models/mart_analytics/hex_ready/math_8_cohort_tracking.sql"
    ).read_text()
    assert "COUNT(DISTINCT student_id_hash) as student_count" in m8

    chronic_feat = (
        REPO_ROOT
        / "oss_framework/dbt/models/mart_features/features/fct_chronic_absence_features.sql"
    ).read_text()
    assert "unique_key=['student_id_hash', 'academic_year']" in chronic_feat
    assert "ds.academic_year = a30.academic_year" in chronic_feat

    dim_stu = (REPO_ROOT / "oss_framework/dbt/models/mart_core/core/dim_students.sql").read_text()
    assert "sed_status" in dim_stu
    assert "sped_status" in dim_stu


def test_main_raw_views_plaintext_allowlist() -> None:
    """Audit the live warehouse: plaintext identifier columns may exist ONLY in
    the Stage-1 raw landing objects — the dlt base tables (``*stage1.raw_*``)
    and the ``main.raw_*`` sync views — and only within the exact allowlist
    recorded in SECURITY.md ("Accepted Deviation: Plaintext Identifiers in
    Stage-1 Raw Landing Objects"). Any new plaintext PII column that reaches
    Stage 1 fails here until the deviation note and this gate are consciously
    extended."""
    import os
    import re

    import duckdb
    import pytest

    from oss_framework.connectors.mappings.aeries_to_canonical import (
        STUDENT_STAGE1_ALLOWLIST,
    )

    db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")
    if not Path(db_path).exists():
        pytest.skip("no local warehouse to audit")

    # Plaintext identifier columns sanctioned by the SECURITY.md deviation note.
    allowed_plaintext: dict[str, set[str]] = {
        "raw_students": {"student_id", "first_name", "last_name", "date_of_birth"},
        "raw_attendance": {"student_id"},
        "raw_academic_records": {"student_id"},
        "raw_discipline": {"student_id"},
        "raw_enrollment": {"student_id"},
    }
    _dlt_meta = re.compile(r"^_dlt")
    # Any column that looks like direct-identifier PII outside the sanctioned set fails.
    # Anchored on string/underscore edges so compound names (e.g. "ethnicity"
    # containing "city") do not false-positive while suffix forms
    # ("home_address", "cell_phone") still match.
    pii_pattern = re.compile(
        r"(^|_)(first_name|last_name|middle_name|date_of_birth|birth_date|email|"
        r"phone|address|street|city|zipcode|zip_code|zip|postal|ssn|state_student_id|"
        r"parent|guardian|contact)(_[0-9]*|[0-9]*$)",
        re.IGNORECASE,
    )

    con = duckdb.connect(db_path, read_only=True)
    try:
        raw_objects = con.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE starts_with(table_name, 'raw_')
              AND (table_schema = 'main' OR table_schema LIKE '%stage1')
            ORDER BY 1, 2
            """
        ).fetchall()
        columns_by_object = {
            (schema, table): [
                row[0]
                for row in con.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = ? AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [schema, table],
                ).fetchall()
            ]
            for schema, table in raw_objects
        }
    finally:
        con.close()

    if not raw_objects:
        pytest.skip("no Stage-1 raw_* objects in this warehouse")

    violations: list[str] = []
    for (schema, table), columns in columns_by_object.items():
        benign = {c for c in columns if not _dlt_meta.match(c)}
        if table == "raw_students":
            outside_allowlist = benign - set(STUDENT_STAGE1_ALLOWLIST)
            if outside_allowlist:
                violations.append(
                    f"{schema}.{table}: columns outside STUDENT_STAGE1_ALLOWLIST: {sorted(outside_allowlist)}"
                )

        sanctioned = allowed_plaintext.get(table, set())
        for column in benign:
            if pii_pattern.search(column) and column not in sanctioned:
                violations.append(
                    f"{schema}.{table}.{column}: plaintext PII column not in SECURITY.md allowlist"
                )

    assert not violations, "Stage-1 plaintext allowlist violations: " + "; ".join(violations)
