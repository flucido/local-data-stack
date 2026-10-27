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
