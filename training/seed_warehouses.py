"""
seed_warehouses.py — Realistic Seeded K-12 Education DuckDB Warehouse Builder & Calibration/Holdout Generator.

Populates realistic data across all 20 K-12 Education tables (`main_core`, `main_analytics`, `main_staging`):
  - Ensures Hop 1 SQL validation and Hop 2 `compute_result_summary` always observe realistic
    non-zero `row_count`, `distinct_count`, `min`/`max` bounds, and `sample_rows`.
  - Can also enrich `oss_framework/data/analytics.duckdb` in-place so local evaluations
    have complete `2021-2022` through `2024-2025` Aeries cohorts and `equity_by_race` subgroups.
  - Generates `training/calibration_sql_genui.txt` (200 calibration ChatML examples for
    `llama-imatrix`) and `nl_query/eval_two_hop_holdout.jsonl` (30 held-out K-12 Two-Hop benchmarks).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "nl_query") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "nl_query"))

from training.schema_pruner import (  # noqa: E402
    format_pruned_ddl,
    load_unified_schema,
    select_training_tables_with_distractors,
)

SCHOOLS = [
    (
        "SCH1",
        "Lincoln High School",
        "01612590134521",
        "Oakland Unified",
        "Oakland",
        "Alameda",
        37.8044,
        -122.2712,
    ),
    (
        "SCH2",
        "Washington Middle School",
        "19647336058214",
        "Los Angeles Unified",
        "Los Angeles",
        "Los Angeles",
        34.0522,
        -118.2437,
    ),
    (
        "SCH3",
        "Roosevelt Elementary",
        "37683386039812",
        "San Diego Unified",
        "San Diego",
        "San Diego",
        32.7157,
        -117.1611,
    ),
    (
        "SCH4",
        "Jefferson STEM Academy",
        "43696664334120",
        "San Jose Unified",
        "San Jose",
        "Santa Clara",
        37.3382,
        -121.8863,
    ),
    (
        "SCH5",
        "Chavez Charter Prep",
        "01612590198234",
        "Oakland Unified",
        "Oakland",
        "Alameda",
        37.7749,
        -122.2241,
    ),
    (
        "SCH6",
        "Oak Valley High",
        "34674393435610",
        "Sacramento City Unified",
        "Sacramento",
        "Sacramento",
        38.5816,
        -121.4944,
    ),
]

RACES = [
    ("Hispanic/Latino", "Hispanic", "700"),
    ("White", "Not Hispanic", "500"),
    ("Asian", "Not Hispanic", "200"),
    ("Black", "Not Hispanic", "600"),
    ("Two or More Races", "Not Hispanic", "999"),
]

REPORTING_CATEGORIES = [
    ("TA", "All Students", False, False, False),
    ("RA", "Asian", True, False, False),
    ("RB", "Black/African American", True, False, False),
    ("RH", "Hispanic/Latino", True, False, False),
    ("RW", "White", True, False, False),
    ("SE", "Socioeconomically Disadvantaged", False, False, True),
    ("EL", "English Learners", False, False, True),
    ("SWD", "Students with Disabilities", False, False, True),
    ("HOM", "Homeless", False, False, True),
    ("FOS", "Foster Youth", False, False, True),
    ("GM", "Male", False, True, False),
    ("GF", "Female", False, True, False),
]

INCIDENT_TYPES = [
    ("Defiance", "Minor", "Parent Conference"),
    ("Fighting", "Moderate", "In-School Suspension"),
    ("Bullying", "Moderate", "Out-of-School Suspension"),
    ("Weapon", "Serious", "Out-of-School Suspension"),
    ("Substance", "Moderate", "Out-of-School Suspension"),
    ("Theft", "Minor", "Restitution"),
    ("Vandalism", "Minor", "Community Service"),
    ("Harassment", "Moderate", "Out-of-School Suspension"),
]


def seed_k12_warehouse(conn: duckdb.DuckDBPyConnection) -> None:
    """Create and seed all 20 K-12 Education warehouse tables with realistic multi-year rows."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS main_core;")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main_analytics;")
    conn.execute("CREATE SCHEMA IF NOT EXISTS main_staging;")

    # 1. main_core.dim_schools
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.dim_schools (
            school_id VARCHAR,
            school_name VARCHAR,
            cds_code VARCHAR,
            cde_school_name VARCHAR,
            cde_district_name VARCHAR,
            cde_city VARCHAR,
            cde_county VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            match_method VARCHAR,
            match_confidence DOUBLE,
            is_mapped BOOLEAN,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )
    school_rows = [
        (
            sid,
            sname,
            cds,
            sname,
            dname,
            city,
            county,
            lat,
            lon,
            "exact_name",
            0.99,
            True,
            "2026-06-15 12:00:00+00",
        )
        for sid, sname, cds, dname, city, county, lat, lon in SCHOOLS
    ]
    conn.executemany(
        "INSERT INTO main_core.dim_schools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        school_rows,
    )

    # 2. main_core.dim_students, fact_attendance, fact_enrollment, fact_academic_records, fact_discipline
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.dim_students (
            student_id_hash VARCHAR,
            age_at_event INTEGER,
            gender VARCHAR,
            ethnicity VARCHAR,
            race_code_1 VARCHAR,
            race_code_2 VARCHAR,
            race_code_3 VARCHAR,
            race_code_4 VARCHAR,
            race_code_5 VARCHAR,
            primary_race VARCHAR,
            is_multi_racial BOOLEAN,
            grade_level INTEGER,
            school_id VARCHAR,
            academic_year VARCHAR,
            home_language VARCHAR,
            special_education_flag BOOLEAN,
            ell_status BOOLEAN,
            free_reduced_lunch_flag BOOLEAN,
            homeless_flag BOOLEAN,
            foster_care_flag BOOLEAN,
            section_504_flag BOOLEAN,
            gate_flag BOOLEAN,
            ell_program_flag BOOLEAN,
            cohort VARCHAR,
            high_need_flag BOOLEAN,
            language_support_needed BOOLEAN,
            socioeconomic_risk BOOLEAN,
            housing_risk BOOLEAN,
            enrollment_status VARCHAR,
            pseudonymization_timestamp TIMESTAMP WITH TIME ZONE,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.fact_attendance (
            student_id_hash VARCHAR,
            school_id VARCHAR,
            academic_year VARCHAR,
            days_enrolled BIGINT,
            days_present HUGEINT,
            days_absent HUGEINT,
            days_excused HUGEINT,
            days_unexcused HUGEINT,
            days_tardy HUGEINT,
            days_truancy INTEGER,
            days_suspended INTEGER,
            days_in_school_suspension INTEGER,
            days_complete_independent_study INTEGER,
            days_incomplete_independent_study INTEGER,
            periods_expected INTEGER,
            periods_attended INTEGER,
            periods_excused_absence INTEGER,
            periods_unexcused_absence INTEGER,
            periods_out_of_school_suspension INTEGER,
            periods_in_school_suspension INTEGER,
            attendance_rate DOUBLE,
            absence_rate DOUBLE,
            excused_absence_rate DOUBLE,
            created_at TIMESTAMP,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.fact_academic_records (
            academic_record_sk VARCHAR,
            student_id_hash VARCHAR,
            teacher_id_hash VARCHAR,
            school_id VARCHAR,
            course_id VARCHAR,
            section_id VARCHAR,
            term VARCHAR,
            school_year VARCHAR,
            grade VARCHAR,
            credit_earned DECIMAL(2,1),
            gpa_points DECIMAL(2,1),
            is_passing BOOLEAN,
            created_at TIMESTAMP,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.fact_discipline (
            student_id_hash VARCHAR,
            school_id VARCHAR,
            incident_id VARCHAR,
            academic_year VARCHAR,
            incident_date DATE,
            incident_type VARCHAR,
            severity VARCHAR,
            resolution VARCHAR,
            suspension_days INTEGER,
            suspension_flag INTEGER,
            serious_incident_flag INTEGER,
            created_at TIMESTAMP,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.fact_enrollment (
            enrollment_sk VARCHAR,
            student_id_hash VARCHAR,
            school_id VARCHAR,
            school_year VARCHAR,
            enrollment_date DATE,
            withdrawal_date DATE,
            grade_level INTEGER,
            enrollment_status VARCHAR,
            enrollment_status_derived VARCHAR,
            created_at TIMESTAMP,
            dbt_processed_date TIMESTAMP WITH TIME ZONE
        );
        """
    )

    aeries_years = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    student_rows = []
    att_rows = []
    acad_rows = []
    disc_rows = []
    enr_rows = []

    for yr_idx, acad_yr in enumerate(aeries_years):
        yr_start = int(acad_yr.split("-")[0])
        for s_idx in range(1, 91):  # 90 students per year -> 360 student-year records
            st_hash = f"stu_{s_idx:04d}"
            school_id = SCHOOLS[s_idx % len(SCHOOLS)][0]
            race_name, eth_name, r_code = RACES[s_idx % len(RACES)]
            is_multi = race_name == "Two or More Races"
            gender = "F" if s_idx % 2 == 0 else "M"
            grade_lvl = ((s_idx + yr_idx) % 12) + 1
            age = grade_lvl + 5
            ell = s_idx % 4 == 0
            frl = s_idx % 3 != 0
            sped = s_idx % 7 == 0
            homeless = s_idx % 11 == 0
            foster = s_idx % 19 == 0
            sec504 = s_idx % 13 == 0
            gate = s_idx % 9 == 0
            high_need = ell or frl or sped or homeless
            home_lang = (
                "Spanish" if ell and s_idx % 2 == 0 else ("Vietnamese" if ell else "English")
            )

            student_rows.append(
                (
                    st_hash,
                    age,
                    gender,
                    eth_name,
                    r_code,
                    "500" if is_multi else None,
                    None,
                    None,
                    None,
                    race_name,
                    is_multi,
                    grade_lvl,
                    school_id,
                    acad_yr,
                    home_lang,
                    sped,
                    ell,
                    frl,
                    homeless,
                    foster,
                    sec504,
                    gate,
                    ell,
                    f"Cohort-{yr_start + (12 - grade_lvl)}",
                    high_need,
                    ell,
                    frl,
                    homeless,
                    "Active",
                    "2026-06-15 12:00:00+00",
                    "2026-06-15 12:00:00+00",
                )
            )

            # Attendance: spread across Severe (<0.80), At Risk (0.80-0.90), Satisfactory (>0.90)
            days_enrolled = 180
            if s_idx % 10 == 0:
                days_absent = 42 - yr_idx  # ~0.77 attendance rate (Severe)
            elif s_idx % 5 == 0:
                days_absent = 24 - yr_idx  # ~0.87 attendance rate (At Risk)
            else:
                days_absent = max(1, (s_idx % 14) - yr_idx)  # ~0.93-0.99 (Satisfactory)

            days_present = days_enrolled - days_absent
            days_excused = days_absent // 2
            days_unexcused = days_absent - days_excused
            days_tardy = s_idx % 8
            days_truancy = max(0, days_unexcused - 3)
            days_susp = 2 if s_idx % 6 == 0 else 0
            att_rate = round(days_present / days_enrolled, 4)
            abs_rate = round(days_absent / days_enrolled, 4)
            exc_rate = round(days_excused / days_enrolled, 4)

            att_rows.append(
                (
                    st_hash,
                    school_id,
                    acad_yr,
                    days_enrolled,
                    days_present,
                    days_absent,
                    days_excused,
                    days_unexcused,
                    days_tardy,
                    days_truancy,
                    days_susp,
                    1 if days_susp > 0 else 0,
                    0,
                    0,
                    1080,
                    days_present * 6,
                    days_excused * 6,
                    days_unexcused * 6,
                    days_susp * 6,
                    0,
                    att_rate,
                    abs_rate,
                    exc_rate,
                    "2026-06-15 12:00:00",
                    "2026-06-15 12:00:00+00",
                )
            )

            enr_rows.append(
                (
                    f"enr_{acad_yr}_{st_hash}",
                    st_hash,
                    school_id,
                    acad_yr,
                    f"{yr_start}-08-20",
                    None,
                    grade_lvl,
                    "Active",
                    "Enrolled",
                    "2026-06-15 12:00:00",
                    "2026-06-15 12:00:00+00",
                )
            )

            # Academic records: 2 courses per student-year, with slight positive trend over yr_idx
            for c_idx, course_id in enumerate(["CRS-MATH-101", "CRS-ELA-101"]):
                if s_idx % 10 == 0:
                    # Chronically absent + failing (<2.0) for combined risk queries (c10)
                    gpa = 1.4 if c_idx == 0 else 1.7
                    letter = "D"
                elif s_idx % 3 == 0:
                    # Honor Roll (3.5+)
                    gpa = min(4.0, round(3.5 + (yr_idx * 0.1) + (c_idx * 0.2), 1))
                    letter = "A"
                else:
                    # On Track (2.0-3.4)
                    gpa = min(3.4, round(2.3 + (yr_idx * 0.15) + ((s_idx % 5) * 0.15), 1))
                    letter = "B" if gpa >= 2.8 else "C"

                acad_rows.append(
                    (
                        f"ar_{acad_yr}_{st_hash}_{c_idx}",
                        st_hash,
                        f"tch_{(s_idx % 15) + 1:03d}",
                        school_id,
                        course_id,
                        f"SEC-{c_idx + 1}",
                        "Fall" if c_idx == 0 else "Spring",
                        acad_yr,
                        letter,
                        5.0 if gpa >= 1.0 else 0.0,
                        gpa,
                        gpa >= 1.0,
                        "2026-06-15 12:00:00",
                        "2026-06-15 12:00:00+00",
                    )
                )

            # Discipline records: students with s_idx % 6 == 0 get 1-4 incidents (so HAVING COUNT(*) >= 3 matches)
            if s_idx % 6 == 0:
                num_incidents = 3 if (s_idx % 18 == 0) else 1
                for inc_i in range(num_incidents):
                    inc_type, sev, res = INCIDENT_TYPES[(s_idx + inc_i) % len(INCIDENT_TYPES)]
                    susp_days = 2 if sev != "Minor" else 0
                    disc_rows.append(
                        (
                            st_hash,
                            school_id,
                            f"inc_{acad_yr}_{st_hash}_{inc_i}",
                            acad_yr,
                            f"{yr_start + 1}-02-{(inc_i * 7 + 5):02d}",
                            inc_type,
                            sev,
                            res,
                            susp_days,
                            1 if susp_days > 0 else 0,
                            1 if sev == "Serious" else 0,
                            "2026-06-15 12:00:00",
                            "2026-06-15 12:00:00+00",
                        )
                    )

    conn.executemany(
        f"INSERT INTO main_core.dim_students VALUES ({', '.join(['?'] * 31)})",
        student_rows,
    )
    conn.executemany(
        f"INSERT INTO main_core.fact_attendance VALUES ({', '.join(['?'] * 25)})",
        att_rows,
    )
    conn.executemany(
        f"INSERT INTO main_core.fact_academic_records VALUES ({', '.join(['?'] * 14)})",
        acad_rows,
    )
    conn.executemany(
        f"INSERT INTO main_core.fact_discipline VALUES ({', '.join(['?'] * 13)})",
        disc_rows,
    )
    conn.executemany(
        f"INSERT INTO main_core.fact_enrollment VALUES ({', '.join(['?'] * 11)})",
        enr_rows,
    )

    # 3. main_core.dim_student_demographics
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_core.dim_student_demographics AS
        SELECT
            grade_level,
            gender,
            ethnicity,
            primary_race,
            is_multi_racial,
            school_id,
            special_education_flag,
            ell_status,
            free_reduced_lunch_flag,
            homeless_flag,
            foster_care_flag,
            section_504_flag,
            gate_flag,
            COUNT(*) AS student_count,
            ROUND(AVG(age_at_event), 2) AS avg_age,
            MIN(age_at_event) AS min_age,
            MAX(age_at_event) AS max_age,
            COUNT(*) AS active_count,
            CAST(1.0 AS FLOAT) AS active_rate
        FROM main_core.dim_students
        GROUP BY
            grade_level, gender, ethnicity, primary_race, is_multi_racial, school_id,
            special_education_flag, ell_status, free_reduced_lunch_flag, homeless_flag,
            foster_care_flag, section_504_flag, gate_flag;
        """
    )

    # 4. main_analytics.equity_by_race
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_analytics.equity_by_race (
            primary_race VARCHAR,
            is_multi_racial BOOLEAN,
            student_count BIGINT,
            special_ed_count HUGEINT,
            frl_count HUGEINT,
            ell_count HUGEINT,
            homeless_count HUGEINT,
            avg_attendance_rate DOUBLE,
            pct_good_attendance DOUBLE,
            avg_days_absent DOUBLE,
            avg_discipline_incidents DOUBLE,
            pct_no_discipline DOUBLE,
            pct_suspended DOUBLE,
            avg_gpa DOUBLE,
            pct_gpa_2_5_plus DOUBLE,
            pct_below_c DOUBLE,
            pct_high_risk DOUBLE,
            pct_moderate_risk DOUBLE,
            pct_low_risk DOUBLE,
            _loaded_at TIMESTAMP WITH TIME ZONE
        );
        INSERT INTO main_analytics.equity_by_race VALUES
            ('Asian', FALSE, 420, 32, 160, 95, 8, 0.958, 89.5, 7.5, 0.18, 92.4, 2.1, 3.42, 86.0, 6.2, 5.4, 14.6, 80.0, '2026-06-15 12:00:00+00'),
            ('Black', FALSE, 310, 48, 215, 22, 19, 0.904, 72.1, 17.2, 0.64, 78.5, 7.8, 2.68, 61.5, 21.0, 18.2, 26.8, 55.0, '2026-06-15 12:00:00+00'),
            ('Hispanic/Latino', FALSE, 680, 92, 510, 260, 38, 0.918, 76.4, 14.8, 0.42, 83.2, 4.9, 2.84, 67.2, 17.5, 14.5, 23.5, 62.0, '2026-06-15 12:00:00+00'),
            ('White', FALSE, 490, 54, 175, 18, 11, 0.942, 84.8, 10.4, 0.27, 88.9, 3.2, 3.21, 79.4, 9.8, 8.1, 17.9, 74.0, '2026-06-15 12:00:00+00'),
            ('Two or More Races', TRUE, 190, 22, 84, 14, 5, 0.931, 81.2, 12.4, 0.33, 86.1, 3.9, 3.08, 74.5, 12.6, 10.2, 19.8, 70.0, '2026-06-15 12:00:00+00');
        """
    )

    # 5. main_analytics.school_summary
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_analytics.school_summary (
            school_id VARCHAR,
            student_count BIGINT,
            pct_special_ed DOUBLE,
            pct_frl DOUBLE,
            pct_ell DOUBLE,
            pct_white DOUBLE,
            pct_hispanic DOUBLE,
            pct_asian DOUBLE,
            pct_black DOUBLE,
            pct_multi_racial DOUBLE,
            avg_grade_level DOUBLE,
            avg_attendance_rate DOUBLE,
            pct_good_attendance DOUBLE,
            avg_discipline_incidents DOUBLE,
            avg_gpa DOUBLE,
            pct_high_risk DOUBLE,
            _loaded_at TIMESTAMP WITH TIME ZONE
        );
        INSERT INTO main_analytics.school_summary VALUES
            ('SCH1', 620, 12.4, 68.5, 24.2, 18.0, 42.0, 16.0, 15.0, 9.0, 10.5, 0.912, 74.8, 0.48, 2.82, 16.4, '2026-06-15 12:00:00+00'),
            ('SCH2', 540, 14.1, 74.2, 28.5, 14.0, 48.0, 14.0, 16.0, 8.0, 7.0, 0.898, 69.2, 0.62, 2.69, 21.8, '2026-06-15 12:00:00+00'),
            ('SCH3', 410, 10.8, 52.0, 19.4, 28.0, 34.0, 20.0, 10.0, 8.0, 3.5, 0.946, 86.1, 0.19, 3.24, 8.2, '2026-06-15 12:00:00+00'),
            ('SCH4', 580, 9.2, 38.4, 14.6, 26.0, 26.0, 32.0, 8.0, 8.0, 9.5, 0.958, 90.4, 0.15, 3.45, 5.6, '2026-06-15 12:00:00+00'),
            ('SCH5', 350, 15.6, 81.0, 34.0, 10.0, 56.0, 12.0, 14.0, 8.0, 10.0, 0.885, 65.4, 0.71, 2.58, 24.5, '2026-06-15 12:00:00+00'),
            ('SCH6', 490, 11.5, 61.2, 21.0, 24.0, 38.0, 18.0, 12.0, 8.0, 10.2, 0.928, 79.6, 0.34, 3.04, 12.9, '2026-06-15 12:00:00+00');
        """
    )

    # 6. main_analytics.v_chronic_absenteeism_risk & v_equity_outcomes_by_demographics
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_analytics.v_chronic_absenteeism_risk AS
        SELECT
            s.student_id_hash AS student_key,
            s.grade_level,
            s.school_id,
            s.academic_year,
            s.gender,
            s.primary_race AS race_ethnicity,
            s.ell_status AS english_learner,
            s.special_education_flag AS special_education,
            s.free_reduced_lunch_flag AS economically_disadvantaged,
            s.homeless_flag,
            a.attendance_rate AS attendance_rate_30d,
            ROUND(a.absence_rate * 0.5, 4) AS unexcused_absence_rate_30d,
            CAST(CASE WHEN a.days_suspended > 0 THEN 2 ELSE 0 END AS HUGEINT) AS discipline_incidents_30d,
            ROUND(a.absence_rate * 2.5, 3) AS absence_discipline_correlation_score,
            a.attendance_rate AS attendance_rate_90d,
            CASE WHEN a.attendance_rate < 0.85 THEN 'Declining' WHEN a.attendance_rate < 0.93 THEN 'Stable' ELSE 'Improving' END AS attendance_trend_90d,
            CASE WHEN a.absence_rate >= 0.10 THEN 1 ELSE 0 END AS chronic_absence_flag,
            ROUND((1.0 - a.attendance_rate) * 100.0, 2) AS chronic_absenteeism_risk_score,
            CAST('2026-06-01' AS DATE) AS snapshot_date,
            CASE WHEN a.attendance_rate < 0.85 THEN 'High' WHEN a.attendance_rate <= 0.92 THEN 'Moderate' ELSE 'Low' END AS risk_level,
            CAST('2026-06-15 12:00:00+00' AS TIMESTAMP WITH TIME ZONE) AS _loaded_at
        FROM main_core.dim_students s
        JOIN main_core.fact_attendance a
          ON s.student_id_hash = a.student_id_hash
         AND s.academic_year = a.academic_year;
        """
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_analytics.v_equity_outcomes_by_demographics AS
        SELECT
            s.primary_race AS race_ethnicity,
            s.ell_status AS english_learner,
            s.special_education_flag AS special_education,
            s.free_reduced_lunch_flag AS economically_disadvantaged,
            COUNT(DISTINCT s.student_id_hash) AS cohort_size,
            ROUND(AVG(CASE WHEN a.attendance_rate >= 0.90 THEN 100.0 ELSE 0.0 END), 2) AS pct_good_attendance,
            ROUND(AVG(CASE WHEN a.days_suspended = 0 THEN 100.0 ELSE 0.0 END), 2) AS pct_no_discipline,
            ROUND(AVG(ar.gpa_points), 2) AS avg_gpa,
            ROUND(AVG(CASE WHEN ar.gpa_points >= 2.5 THEN 100.0 ELSE 0.0 END), 2) AS pct_gpa_2_5_plus,
            ROUND(AVG(CASE WHEN ar.gpa_points < 2.0 THEN 100.0 ELSE 0.0 END), 2) AS pct_below_c,
            CAST('2026-06-15 12:00:00+00' AS TIMESTAMP WITH TIME ZONE) AS _loaded_at
        FROM main_core.dim_students s
        JOIN main_core.fact_attendance a
          ON s.student_id_hash = a.student_id_hash AND s.academic_year = a.academic_year
        JOIN main_core.fact_academic_records ar
          ON s.student_id_hash = ar.student_id_hash AND s.academic_year = ar.school_year
        GROUP BY 1, 2, 3, 4;
        """
    )

    # 7. CDE OBT & Staging tables (`mart_cde_school_accountability` and `stg_cde__*`)
    conn.execute(
        """
        CREATE OR REPLACE TABLE main_analytics.mart_cde_school_accountability (
            cds_code VARCHAR,
            academic_year VARCHAR,
            reporting_category VARCHAR,
            reporting_category_label VARCHAR,
            school_id VARCHAR,
            school_name VARCHAR,
            district_name VARCHAR,
            county_name VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            ca_eligible_enrollment INTEGER,
            ca_chronic_absent_count INTEGER,
            ca_chronic_absent_rate_pct DOUBLE,
            ar_students_with_absences INTEGER,
            ar_avg_days_absent DOUBLE,
            ar_total_days_absent INTEGER,
            ar_pct_excused DOUBLE,
            ar_pct_unexcused DOUBLE,
            ar_pct_oss_absence DOUBLE,
            ar_pct_incomplete_is DOUBLE,
            en_cumulative_enrollment INTEGER,
            su_total_suspensions INTEGER,
            su_unique_students_suspended INTEGER,
            su_suspension_rate_pct DOUBLE,
            su_violent_injury INTEGER,
            su_violent_no_injury INTEGER,
            su_weapons INTEGER,
            su_drug_related INTEGER,
            su_defiance_only INTEGER,
            su_other_reasons INTEGER,
            ex_total_expulsions INTEGER,
            ex_unique_students_expelled INTEGER,
            ex_expulsion_rate_pct DOUBLE,
            hs_cumulative_enrollment INTEGER,
            hs_homeless_count INTEGER,
            hs_doubled_up_pct DOUBLE,
            hs_shelters_pct DOUBLE,
            hs_hotels_pct DOUBLE,
            hs_unsheltered_pct DOUBLE,
            frpm_enrollment_k12 INTEGER,
            frpm_free_count_k12 INTEGER,
            frpm_free_pct_k12 DOUBLE,
            frpm_reduced_count_k12 INTEGER,
            frpm_reduced_pct_k12 DOUBLE,
            ela_currdenom INTEGER,
            ela_currstatus DOUBLE,
            ela_status VARCHAR,
            elpac_progressed_pct DOUBLE,
            elpac_maintained_pl4_pct DOUBLE,
            elpac_declined_pct DOUBLE,
            sbac_mean_scale_score DOUBLE,
            sbac_pct_standard_exceeded DOUBLE,
            sbac_pct_standard_met_above DOUBLE,
            sbac_pct_standard_not_met DOUBLE,
            sbac_students_tested INTEGER,
            rs_mechanical_restraints INTEGER,
            rs_physical_restraints INTEGER,
            rs_seclusions INTEGER,
            dbt_loaded_at TIMESTAMP WITH TIME ZONE,
            is_suppressed BOOLEAN,
            data_domains_present INTEGER,
            has_cde_data BOOLEAN,
            is_race_ethnicity_subgroup BOOLEAN,
            is_gender_subgroup BOOLEAN,
            is_atrisk_subgroup BOOLEAN,
            is_grade_level_subgroup BOOLEAN,
            aggregate_level VARCHAR,
            aggregate_level_label VARCHAR
        );
        """
    )

    cde_years = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    mart_rows = []
    ca_stg_rows = []
    su_stg_rows = []
    en_stg_rows = []
    frpm_stg_rows = []
    hom_stg_rows = []
    ex_stg_rows = []
    caspp_stg_rows = []
    rs_stg_rows = []

    for y_idx, cde_yr in enumerate(cde_years):
        # Include school-level ('S'), district-level ('D'), county-level ('C'), and state-level ('T') rows
        for s_idx, (sid, sname, cds, dname, _city, county, lat, lon) in enumerate(SCHOOLS):
            c_code = cds[:2]
            d_code = cds[2:7]
            s_code = cds[7:]
            for rc_idx, (rc_code, rc_label, is_race, is_gen, is_risk) in enumerate(
                REPORTING_CATEGORIES
            ):
                enr = 520 + (s_idx * 45) - (rc_idx * 25) + (y_idx * 12)
                enr = max(60, enr)
                # Chronic absenteeism: make 2021-22 highest, improving by 2023-24
                base_ca = 24.5 - (y_idx * 2.1) + (s_idx * 2.8) + (rc_idx * 0.9)
                ca_rate = round(max(4.2, min(48.0, base_ca)), 2)
                ca_cnt = int(round(enr * ca_rate / 100.0))

                # Suspensions: make SCH4 have 0 suspensions for zero-suspension queries (g20)
                if s_idx == 3:
                    su_total = 0
                    su_uniq = 0
                    su_rate = 0.0
                else:
                    su_rate = round(
                        max(0.8, 5.2 - (y_idx * 0.3) + (s_idx * 0.9) + (rc_idx * 0.25)), 2
                    )
                    su_uniq = max(1, int(round(enr * su_rate / 100.0)))
                    su_total = int(su_uniq * 1.25)

                frpm_free_pct = round(min(92.0, 42.0 + s_idx * 7.5 + (rc_idx * 1.1)), 2)
                frpm_free_cnt = int(round(enr * frpm_free_pct / 100.0))
                frpm_red_cnt = int(round(enr * 0.08))
                frpm_red_pct = 8.0

                sbac_met = round(
                    min(88.0, max(22.0, 58.0 - s_idx * 4.2 + y_idx * 1.8 - rc_idx * 1.2)), 2
                )
                sbac_exc = round(sbac_met * 0.42, 2)
                sbac_not = round(max(5.0, 100.0 - sbac_met - 22.0), 2)
                sbac_mean = round(2480.0 + sbac_met * 1.8, 1)

                hom_cnt = max(2, int(enr * (0.04 + s_idx * 0.01)))
                phys_rest = 3 if (s_idx in (0, 3) and rc_code == "TA") else 0

                for agg_lvl, agg_lbl in [("S", "School"), ("D", "District"), ("T", "State")]:
                    if agg_lvl != "S" and s_idx > 2:
                        continue
                    mart_rows.append(
                        (
                            cds,
                            cde_yr,
                            rc_code,
                            rc_label,
                            sid,
                            sname,
                            dname,
                            county,
                            lat,
                            lon,
                            enr,
                            ca_cnt,
                            ca_rate,
                            ca_cnt * 2,
                            11.4,
                            ca_cnt * 18,
                            58.0,
                            38.0,
                            2.5,
                            1.5,
                            enr,
                            su_total,
                            su_uniq,
                            su_rate,
                            1 if su_total > 4 else 0,
                            max(0, su_total // 3),
                            1 if su_total > 8 else 0,
                            max(0, su_total // 5),
                            max(0, su_total // 4),
                            max(0, su_total // 6),
                            1 if su_total > 12 else 0,
                            1 if su_total > 12 else 0,
                            round(0.2 if su_total > 12 else 0.0, 2),
                            enr,
                            hom_cnt,
                            72.0,
                            14.0,
                            8.0,
                            6.0,
                            enr,
                            frpm_free_cnt,
                            frpm_free_pct,
                            frpm_red_cnt,
                            frpm_red_pct,
                            enr,
                            round(sbac_met - 50.0, 1),
                            "Medium",
                            48.5,
                            32.0,
                            19.5,
                            sbac_mean,
                            sbac_exc,
                            sbac_met,
                            sbac_not,
                            int(enr * 0.95),
                            0,
                            phys_rest,
                            0,
                            "2026-06-15 12:00:00+00",
                            False,
                            7,
                            True,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                            agg_lvl,
                            agg_lbl,
                        )
                    )

                    ca_stg_rows.append(
                        (
                            cde_yr,
                            agg_lvl,
                            cds,
                            c_code,
                            d_code,
                            s_code,
                            county,
                            dname,
                            sname,
                            "No",
                            "No",
                            rc_code,
                            rc_label,
                            enr,
                            ca_cnt,
                            ca_rate,
                            False,
                            False,
                            "2026-06-15 12:00:00+00",
                            "cde_ca.txt",
                            "load_1",
                            "2026-06-15 12:00:00+00",
                            agg_lbl,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                            "All Grades",
                        )
                    )

                    su_stg_rows.append(
                        (
                            cde_yr,
                            agg_lvl,
                            cds,
                            c_code,
                            d_code,
                            s_code,
                            county,
                            dname,
                            sname,
                            "No",
                            rc_code,
                            enr,
                            su_total,
                            su_uniq,
                            max(0, su_uniq // 4),
                            su_rate,
                            1 if su_total > 4 else 0,
                            max(0, su_total // 3),
                            1 if su_total > 8 else 0,
                            max(0, su_total // 5),
                            max(0, su_total // 4),
                            max(0, su_total // 6),
                            False,
                            False,
                            "2026-06-15 12:00:00+00",
                            "cde_su.txt",
                            "2026-06-15 12:00:00+00",
                            rc_label,
                            agg_lbl,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                        )
                    )

                    en_stg_rows.append(
                        (
                            cde_yr,
                            agg_lvl,
                            cds,
                            c_code,
                            d_code,
                            s_code,
                            county,
                            dname,
                            sname,
                            "No",
                            rc_code,
                            enr,
                            False,
                            False,
                            "2026-06-15 12:00:00+00",
                            "cde_en.txt",
                            "2026-06-15 12:00:00+00",
                            rc_label,
                            agg_lbl,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                        )
                    )

                    hom_stg_rows.append(
                        (
                            cde_yr,
                            agg_lvl,
                            cds,
                            c_code,
                            d_code,
                            s_code,
                            county,
                            dname,
                            sname,
                            "No",
                            "No",
                            rc_code,
                            enr,
                            hom_cnt,
                            int(hom_cnt * 0.70),
                            int(hom_cnt * 0.15),
                            int(hom_cnt * 0.10),
                            max(0, hom_cnt - int(hom_cnt * 0.95)),
                            0,
                            70.0,
                            15.0,
                            10.0,
                            5.0,
                            0.0,
                            False,
                            False,
                            "2026-06-15 12:00:00+00",
                            "cde_hom.txt",
                            "2026-06-15 12:00:00+00",
                            rc_label,
                            agg_lbl,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                        )
                    )

                    ex_stg_rows.append(
                        (
                            cde_yr,
                            agg_lvl,
                            cds,
                            c_code,
                            d_code,
                            s_code,
                            county,
                            dname,
                            sname,
                            "No",
                            rc_code,
                            enr,
                            1 if su_total > 12 else 0,
                            1 if su_total > 12 else 0,
                            0,
                            round(0.2 if su_total > 12 else 0.0, 2),
                            0,
                            1 if su_total > 12 else 0,
                            0,
                            0,
                            0,
                            0,
                            False,
                            False,
                            "2026-06-15 12:00:00+00",
                            "cde_ex.txt",
                            "2026-06-15 12:00:00+00",
                            rc_label,
                            agg_lbl,
                            is_race,
                            is_gen,
                            is_risk,
                            False,
                        )
                    )

                frpm_stg_rows.append(
                    (
                        cds,
                        c_code,
                        d_code,
                        s_code,
                        county,
                        dname,
                        sname,
                        cde_yr,
                        "Unified",
                        "High School",
                        "Traditional",
                        "Standard",
                        "No",
                        None,
                        None,
                        "N",
                        "K",
                        "12",
                        enr,
                        frpm_free_cnt,
                        frpm_free_pct,
                        frpm_free_cnt + frpm_red_cnt,
                        min(99.0, frpm_free_pct + frpm_red_pct),
                        enr,
                        frpm_free_cnt,
                        frpm_free_pct,
                        frpm_free_cnt + frpm_red_cnt,
                        min(99.0, frpm_free_pct + frpm_red_pct),
                        "Y",
                        "2026-06-15 12:00:00+00",
                        "cde_frpm.txt",
                        rc_code,
                        rc_label,
                        "2026-06-15 12:00:00+00",
                        is_race,
                        is_gen,
                        is_risk,
                        False,
                    )
                )

                caspp_stg_rows.append(
                    (
                        cds,
                        c_code,
                        d_code,
                        s_code,
                        rc_code,
                        rc_label,
                        cde_yr,
                        "SBAC-ELA",
                        enr,
                        int(enr * 0.95),
                        enr,
                        int(enr * 0.95),
                        int(enr * 0.95),
                        sbac_mean,
                        sbac_exc,
                        round(sbac_met - sbac_exc, 2),
                        sbac_met,
                        22.0,
                        sbac_not,
                        sbac_exc,
                        45.0,
                        sbac_not,
                        sbac_exc,
                        45.0,
                        sbac_not,
                        sbac_exc,
                        45.0,
                        sbac_not,
                        sbac_exc,
                        45.0,
                        sbac_not,
                        "School",
                        is_race,
                        is_gen,
                        is_risk,
                        False,
                        "2026-06-15 12:00:00",
                        "cde_caspp.txt",
                        "2026-06-15 12:00:00+00",
                    )
                )

                rs_stg_rows.append(
                    (
                        cds,
                        c_code,
                        d_code,
                        s_code,
                        county,
                        dname,
                        sname,
                        cde_yr,
                        "S",
                        "N",
                        rc_code,
                        rc_label,
                        0,
                        0,
                        phys_rest,
                        phys_rest,
                        0,
                        "2026-06-15 12:00:00+00",
                        "cde_rs.txt",
                        "School",
                        is_race,
                        is_gen,
                        is_risk,
                        False,
                    )
                )

    conn.executemany(
        f"INSERT INTO main_analytics.mart_cde_school_accountability VALUES ({', '.join(['?'] * 68)})",
        mart_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__chronic_absenteeism (
            academic_year VARCHAR, aggregate_level VARCHAR, cds_code VARCHAR, county_code VARCHAR,
            district_code VARCHAR, school_code VARCHAR, county_name VARCHAR, district_name VARCHAR,
            school_name VARCHAR, charter_school VARCHAR, dashboard_alternative_school_status VARCHAR,
            reporting_category VARCHAR, reporting_category_label VARCHAR, eligible_enrollment INTEGER,
            chronic_absent_count INTEGER, chronic_absent_rate_pct DOUBLE, is_suppressed BOOLEAN,
            is_small_n BOOLEAN, dlt_loaded_at TIMESTAMP WITH TIME ZONE, source_filename VARCHAR,
            dlt_load_id VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE, aggregate_level_label VARCHAR,
            is_race_ethnicity_subgroup BOOLEAN, is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN,
            is_grade_level_subgroup BOOLEAN, grade_level_group VARCHAR
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__chronic_absenteeism VALUES ({', '.join(['?'] * 28)})",
        ca_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__suspension (
            academic_year VARCHAR, aggregate_level VARCHAR, cds_code VARCHAR, county_code VARCHAR,
            district_code VARCHAR, school_code VARCHAR, county_name VARCHAR, district_name VARCHAR,
            school_name VARCHAR, charter_school VARCHAR, reporting_category VARCHAR,
            cumulative_enrollment INTEGER, total_suspensions INTEGER,
            unduplicated_count_of_students_suspended_total INTEGER,
            unduplicated_count_of_students_suspended_defiance_only INTEGER,
            suspension_rate_total DOUBLE, suspension_count_violent_incident_injury INTEGER,
            suspension_count_violent_incident_no_injury INTEGER,
            suspension_count_weapons_possession INTEGER,
            suspension_count_illicit_drug_related INTEGER,
            suspension_count_defiance_only INTEGER, suspension_count_other_reasons INTEGER,
            is_suppressed BOOLEAN, is_small_n BOOLEAN, _loaded_at TIMESTAMP WITH TIME ZONE,
            _source_file VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE,
            reporting_category_label VARCHAR, aggregate_level_label VARCHAR,
            is_race_ethnicity_subgroup BOOLEAN, is_gender_subgroup BOOLEAN,
            is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__suspension VALUES ({', '.join(['?'] * 33)})",
        su_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__enrollment (
            academic_year VARCHAR, aggregate_level VARCHAR, cds_code VARCHAR, county_code VARCHAR,
            district_code VARCHAR, school_code VARCHAR, county_name VARCHAR, district_name VARCHAR,
            school_name VARCHAR, charter_school VARCHAR, reporting_category VARCHAR,
            cumulative_enrollment INTEGER, is_suppressed BOOLEAN, is_small_n BOOLEAN,
            _loaded_at TIMESTAMP WITH TIME ZONE, _source_file VARCHAR,
            dbt_loaded_at TIMESTAMP WITH TIME ZONE, reporting_category_label VARCHAR,
            aggregate_level_label VARCHAR, is_race_ethnicity_subgroup BOOLEAN,
            is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__enrollment VALUES ({', '.join(['?'] * 23)})",
        en_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__frpm (
            cds_code VARCHAR, county_code VARCHAR, district_code VARCHAR, school_code VARCHAR,
            county_name VARCHAR, district_name VARCHAR, school_name VARCHAR, academic_year VARCHAR,
            district_type VARCHAR, school_type VARCHAR, educational_option_type VARCHAR,
            nslp_provision_status VARCHAR, charter_school VARCHAR, charter_number VARCHAR,
            charter_funding_type VARCHAR, irc VARCHAR, low_grade VARCHAR, high_grade VARCHAR,
            enrollment_k12 INTEGER, free_meal_count_k12 INTEGER, percent_eligible_free_k12 DOUBLE,
            frpm_count_k12 INTEGER, percent_eligible_frpm_k12 DOUBLE, enrollment_ages_5_17 INTEGER,
            free_meal_count_ages_5_17 INTEGER, percent_eligible_free_ages_5_17 DOUBLE,
            frpm_count_ages_5_17 INTEGER, percent_eligible_frpm_ages_5_17 DOUBLE,
            calpads_certification_status VARCHAR, dlt_loaded_at TIMESTAMP WITH TIME ZONE,
            source_filename VARCHAR, reporting_category VARCHAR, reporting_category_label VARCHAR,
            dbt_loaded_at TIMESTAMP WITH TIME ZONE, is_race_ethnicity_subgroup BOOLEAN,
            is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__frpm VALUES ({', '.join(['?'] * 38)})",
        frpm_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__homeless_enrollment (
            academic_year VARCHAR, aggregate_level VARCHAR, cds_code VARCHAR, county_code VARCHAR,
            district_code VARCHAR, school_code VARCHAR, county_name VARCHAR, district_name VARCHAR,
            school_name VARCHAR, charter_school VARCHAR, dashboard_alternative_school_status VARCHAR,
            reporting_category VARCHAR, cumulative_enrollment INTEGER,
            homeless_student_enrollment INTEGER, temporarily_doubled_up INTEGER,
            temporary_shelters INTEGER, hotels_motels INTEGER, temporarily_unsheltered INTEGER,
            missing_unknown INTEGER, temporarily_doubled_up_percent DOUBLE,
            temporary_shelters_percent DOUBLE, hotels_motels_percent DOUBLE,
            temporarily_unsheltered_percent DOUBLE, missing_unknown_percent DOUBLE,
            is_suppressed BOOLEAN, is_small_n BOOLEAN, _loaded_at TIMESTAMP WITH TIME ZONE,
            _source_file VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE,
            reporting_category_label VARCHAR, aggregate_level_label VARCHAR,
            is_race_ethnicity_subgroup BOOLEAN, is_gender_subgroup BOOLEAN,
            is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__homeless_enrollment VALUES ({', '.join(['?'] * 35)})",
        hom_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__expulsion (
            academic_year VARCHAR, aggregate_level VARCHAR, cds_code VARCHAR, county_code VARCHAR,
            district_code VARCHAR, school_code VARCHAR, county_name VARCHAR, district_name VARCHAR,
            school_name VARCHAR, charter_school VARCHAR, reporting_category VARCHAR,
            cumulative_enrollment INTEGER, total_expulsions INTEGER,
            unduplicated_count_of_students_expelled_total INTEGER,
            unduplicated_count_of_students_expelled_defiance_only INTEGER,
            expulsion_rate_total DOUBLE, expulsion_count_violent_incident_injury INTEGER,
            expulsion_count_violent_incident_no_injury INTEGER,
            expulsion_count_weapons_possession INTEGER,
            expulsion_count_illicit_drug_related INTEGER,
            expulsion_count_defiance_only INTEGER, expulsion_count_other_reasons INTEGER,
            is_suppressed BOOLEAN, is_small_n BOOLEAN, _loaded_at TIMESTAMP WITH TIME ZONE,
            _source_file VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE,
            reporting_category_label VARCHAR, aggregate_level_label VARCHAR,
            is_race_ethnicity_subgroup BOOLEAN, is_gender_subgroup BOOLEAN,
            is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__expulsion VALUES ({', '.join(['?'] * 33)})",
        ex_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__assessment_caspp (
            cds_code VARCHAR, county_code VARCHAR, district_code VARCHAR, school_code VARCHAR,
            reporting_category VARCHAR, reporting_category_label VARCHAR, academic_year VARCHAR,
            test_type VARCHAR, total_tested_at_reporting_level INTEGER,
            total_tested_with_scores_at_reporting_level INTEGER, students_enrolled INTEGER,
            students_tested INTEGER, students_with_scores INTEGER, mean_scale_score DOUBLE,
            pct_standard_exceeded DOUBLE, pct_standard_met DOUBLE, pct_standard_met_and_above DOUBLE,
            pct_standard_nearly_met DOUBLE, pct_standard_not_met DOUBLE,
            area_1_pct_above_standard DOUBLE, area_1_pct_near_standard DOUBLE, area_1_pct_below_standard DOUBLE,
            area_2_pct_above_standard DOUBLE, area_2_pct_near_standard DOUBLE, area_2_pct_below_standard DOUBLE,
            area_3_pct_above_standard DOUBLE, area_3_pct_near_standard DOUBLE, area_3_pct_below_standard DOUBLE,
            area_4_pct_above_standard DOUBLE, area_4_pct_near_standard DOUBLE, area_4_pct_below_standard DOUBLE,
            aggregate_level_label VARCHAR, is_race_ethnicity_subgroup BOOLEAN,
            is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN,
            dlt_loaded_at TIMESTAMP, source_filename VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__assessment_caspp VALUES ({', '.join(['?'] * 39)})",
        caspp_stg_rows,
    )

    conn.execute(
        """
        CREATE OR REPLACE TABLE main_staging.stg_cde__restraint_seclusion (
            cds_code VARCHAR, county_code VARCHAR, district_code VARCHAR, school_code VARCHAR,
            county_name VARCHAR, district_name VARCHAR, school_name VARCHAR, academic_year VARCHAR,
            aggregate_level VARCHAR, nps VARCHAR, reporting_category VARCHAR,
            reporting_category_label VARCHAR, count_of_mechanical_restraints INTEGER,
            unduplicated_count_of_students_mechanical INTEGER, count_of_physical_restraints INTEGER,
            unduplicated_count_of_students_physical INTEGER, count_of_seclusions INTEGER,
            dlt_loaded_at TIMESTAMP WITH TIME ZONE, source_filename VARCHAR,
            aggregate_level_label VARCHAR, is_race_ethnicity_subgroup BOOLEAN,
            is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN
        );
        """
    )
    conn.executemany(
        f"INSERT INTO main_staging.stg_cde__restraint_seclusion VALUES ({', '.join(['?'] * 24)})",
        rs_stg_rows,
    )


def seed_all_warehouses(conn: duckdb.DuckDBPyConnection) -> None:
    """Seed all 20 K-12 Education warehouse tables (`main_core`, `main_analytics`, `main_staging`)."""
    seed_k12_warehouse(conn)


def enrich_existing_warehouse(db_path: str | Path) -> None:
    """Enrich `oss_framework/data/analytics.duckdb` so local evaluations have complete
    `2021-2022` through `2024-2025` cohorts in `main_core` and full `equity_by_race` rows.
    """
    mem = duckdb.connect(":memory:")
    seed_all_warehouses(mem)

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        # Replace `main_core` tables and `equity_by_race`/`school_summary` with multi-year seeded tables
        # if `2023-2024` is missing from `main_core.dim_students`.
        has_2324 = conn.execute(
            "SELECT COUNT(*) FROM main_core.dim_students WHERE academic_year = '2023-2024'"
        ).fetchone()[0]
        if has_2324 == 0:
            for tbl in [
                "main_core.dim_schools",
                "main_core.dim_students",
                "main_core.dim_student_demographics",
                "main_core.fact_attendance",
                "main_core.fact_academic_records",
                "main_core.fact_discipline",
                "main_core.fact_enrollment",
                "main_analytics.equity_by_race",
                "main_analytics.school_summary",
                "main_analytics.v_chronic_absenteeism_risk",
                "main_analytics.v_equity_outcomes_by_demographics",
            ]:
                rows = mem.execute(f"SELECT * FROM {tbl}").fetchall()
                conn.execute(f"DELETE FROM {tbl}")
                if rows:
                    placeholders = ", ".join(["?"] * len(rows[0]))
                    conn.executemany(f"INSERT INTO {tbl} VALUES ({placeholders})", rows)

        # Populate stg_cde__assessment_caspp if empty
        caspp_cnt = conn.execute(
            "SELECT COUNT(*) FROM main_staging.stg_cde__assessment_caspp"
        ).fetchone()[0]
        if caspp_cnt == 0:
            conn.execute("DROP VIEW IF EXISTS main_staging.stg_cde__assessment_caspp")
            conn.execute(
                """
                CREATE OR REPLACE TABLE main_staging.stg_cde__assessment_caspp (
                    cds_code VARCHAR, county_code VARCHAR, district_code VARCHAR, school_code VARCHAR,
                    reporting_category VARCHAR, reporting_category_label VARCHAR, academic_year VARCHAR,
                    test_type VARCHAR, total_tested_at_reporting_level INTEGER,
                    total_tested_with_scores_at_reporting_level INTEGER, students_enrolled INTEGER,
                    students_tested INTEGER, students_with_scores INTEGER, mean_scale_score DOUBLE,
                    pct_standard_exceeded DOUBLE, pct_standard_met DOUBLE, pct_standard_met_and_above DOUBLE,
                    pct_standard_nearly_met DOUBLE, pct_standard_not_met DOUBLE,
                    area_1_pct_above_standard DOUBLE, area_1_pct_near_standard DOUBLE, area_1_pct_below_standard DOUBLE,
                    area_2_pct_above_standard DOUBLE, area_2_pct_near_standard DOUBLE, area_2_pct_below_standard DOUBLE,
                    area_3_pct_above_standard DOUBLE, area_3_pct_near_standard DOUBLE, area_3_pct_below_standard DOUBLE,
                    area_4_pct_above_standard DOUBLE, area_4_pct_near_standard DOUBLE, area_4_pct_below_standard DOUBLE,
                    aggregate_level_label VARCHAR, is_race_ethnicity_subgroup BOOLEAN,
                    is_gender_subgroup BOOLEAN, is_atrisk_subgroup BOOLEAN, is_grade_level_subgroup BOOLEAN,
                    dlt_loaded_at TIMESTAMP, source_filename VARCHAR, dbt_loaded_at TIMESTAMP WITH TIME ZONE
                );
                """
            )
            caspp_rows = mem.execute(
                "SELECT * FROM main_staging.stg_cde__assessment_caspp"
            ).fetchall()
            if caspp_rows:
                placeholders = ", ".join(["?"] * len(caspp_rows[0]))
                conn.executemany(
                    f"INSERT INTO main_staging.stg_cde__assessment_caspp VALUES ({placeholders})",
                    caspp_rows,
                )

        # Ensure `mart_cde_school_accountability` has non-null `school_name` and `county_name`
        conn.execute(
            """
            UPDATE main_analytics.mart_cde_school_accountability
            SET school_name = COALESCE(school_name, 'School ' || SUBSTR(cds_code, 8, 7)),
                district_name = COALESCE(district_name, 'District ' || SUBSTR(cds_code, 3, 5)),
                county_name = COALESCE(county_name, 'County ' || SUBSTR(cds_code, 1, 2)),
                sbac_pct_standard_met_above = COALESCE(sbac_pct_standard_met_above, 52.4)
            WHERE school_name IS NULL OR county_name IS NULL OR sbac_pct_standard_met_above IS NULL;
            """
        )
    finally:
        conn.close()
        mem.close()


# ── Holdout & Calibration Dataset Builders (100% K-12 Education) ────────

K12_EXTRA_HOLDOUT_ITEMS = [
    {
        "id": "h21",
        "question": "Show student count and average chronic absenteeism risk score by risk level in 2023-2024",
        "gold_sql": "SELECT risk_level, COUNT(*) AS student_count, ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score\nFROM main_analytics.v_chronic_absenteeism_risk\nWHERE academic_year = '2023-2024'\nGROUP BY risk_level\nORDER BY avg_risk_score DESC",
        "path": "analytics",
        "difficulty": "easy",
        "label": "v_chronic_absenteeism_risk — risk level breakdown",
    },
    {
        "id": "h22",
        "question": "Compare average GPA and percentage with good attendance by race/ethnicity for English Learners",
        "gold_sql": "SELECT race_ethnicity, SUM(cohort_size) AS total_students, ROUND(AVG(avg_gpa), 2) AS mean_gpa, ROUND(AVG(pct_good_attendance), 2) AS mean_pct_good_attendance\nFROM main_analytics.v_equity_outcomes_by_demographics\nWHERE english_learner = TRUE\nGROUP BY race_ethnicity\nORDER BY mean_gpa DESC",
        "path": "analytics",
        "difficulty": "medium",
        "label": "v_equity_outcomes_by_demographics — EL outcomes by race",
    },
    {
        "id": "h23",
        "question": "What are the total suspensions and suspension rates by reporting category across schools in 2023-24?",
        "gold_sql": "SELECT reporting_category_label, SUM(total_suspensions) AS total_suspensions, ROUND(AVG(suspension_rate_total), 2) AS avg_suspension_rate\nFROM main_staging.stg_cde__suspension\nWHERE academic_year = '2023-24' AND aggregate_level = 'S'\nGROUP BY reporting_category_label\nORDER BY avg_suspension_rate DESC",
        "path": "staging",
        "difficulty": "medium",
        "label": "stg_cde__suspension — suspension rate by subgroup",
    },
    {
        "id": "h24",
        "question": "Which districts had the highest free meal eligibility percentage in 2023-24?",
        "gold_sql": "SELECT district_name, ROUND(AVG(percent_eligible_free_k12), 2) AS avg_free_meal_pct, SUM(free_meal_count_k12) AS total_free_meal_students\nFROM main_staging.stg_cde__frpm\nWHERE academic_year = '2023-24' AND reporting_category = 'TA'\nGROUP BY district_name\nORDER BY avg_free_meal_pct DESC\nLIMIT 10",
        "path": "staging",
        "difficulty": "medium",
        "label": "stg_cde__frpm — district free meal eligibility",
    },
    {
        "id": "h25",
        "question": "Show total homeless student enrollment and doubled-up housing counts by county in 2023-24",
        "gold_sql": "SELECT county_name, SUM(homeless_student_enrollment) AS total_homeless, SUM(temporarily_doubled_up) AS total_doubled_up\nFROM main_staging.stg_cde__homeless_enrollment\nWHERE academic_year = '2023-24' AND aggregate_level = 'S' AND reporting_category = 'TA'\nGROUP BY county_name\nORDER BY total_homeless DESC",
        "path": "staging",
        "difficulty": "medium",
        "label": "stg_cde__homeless_enrollment — homeless & doubled-up by county",
    },
    {
        "id": "h26",
        "question": "What is the average CAASPP mean scale score and standard met/exceeded percentage by subgroup in 2023-24?",
        "gold_sql": "SELECT reporting_category_label, ROUND(AVG(mean_scale_score), 1) AS avg_scale_score, ROUND(AVG(pct_standard_met_and_above), 2) AS avg_pct_met_above\nFROM main_staging.stg_cde__assessment_caspp\nWHERE academic_year = '2023-24'\nGROUP BY reporting_category_label\nORDER BY avg_pct_met_above DESC",
        "path": "staging",
        "difficulty": "medium",
        "label": "stg_cde__assessment_caspp — subgroup proficiency",
    },
    {
        "id": "h27",
        "question": "Compare school-level average GPA, attendance rate, and high-risk percentage across all schools in school_summary",
        "gold_sql": "SELECT s.school_id, d.school_name, s.student_count, s.avg_attendance_rate, s.avg_gpa, s.pct_high_risk\nFROM main_analytics.school_summary s\nLEFT JOIN main_core.dim_schools d ON s.school_id = d.school_id\nORDER BY s.pct_high_risk DESC",
        "path": "analytics",
        "difficulty": "easy",
        "label": "school_summary + dim_schools — school risk & GPA overview",
    },
    {
        "id": "h28",
        "question": "How many discipline incidents and total suspension days occurred by incident type and severity in 2023-2024?",
        "gold_sql": "SELECT incident_type, severity, COUNT(*) AS incident_count, SUM(suspension_days) AS total_suspension_days\nFROM main_core.fact_discipline\nWHERE academic_year = '2023-2024'\nGROUP BY incident_type, severity\nORDER BY incident_count DESC",
        "path": "core",
        "difficulty": "easy",
        "label": "fact_discipline — incidents by type and severity",
    },
    {
        "id": "h29",
        "question": "Show active student counts and average age by grade level from dim_student_demographics",
        "gold_sql": "SELECT grade_level, SUM(student_count) AS total_students, ROUND(AVG(avg_age), 2) AS mean_age\nFROM main_core.dim_student_demographics\nGROUP BY grade_level\nORDER BY grade_level ASC",
        "path": "core",
        "difficulty": "easy",
        "label": "dim_student_demographics — students and age by grade",
    },
    {
        "id": "h30",
        "question": "Compare chronic absenteeism rates across academic years for English Learners vs Socioeconomically Disadvantaged students",
        "gold_sql": "SELECT academic_year, reporting_category_label, ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate\nFROM main_analytics.mart_cde_school_accountability\nWHERE reporting_category IN ('EL', 'SE') AND aggregate_level = 'S'\nGROUP BY academic_year, reporting_category_label\nORDER BY academic_year ASC, reporting_category_label ASC",
        "path": "obt",
        "difficulty": "medium",
        "label": "mart_cde_school_accountability — multi-year EL vs SE trend",
    },
]


def generate_two_hop_holdout(output_path: Path) -> int:
    """Create `nl_query/eval_two_hop_holdout.jsonl` with 30 pure K-12 Education benchmark questions."""
    base_eval_path = PROJECT_ROOT / "nl_query" / "eval_test_set.jsonl"
    items: list[dict[str, Any]] = []
    if base_eval_path.exists():
        for line in base_eval_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append(json.loads(line))
    items.extend(K12_EXTRA_HOLDOUT_ITEMS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")
    return len(items)


def generate_calibration_corpus(output_path: Path, n_samples: int = 200) -> int:
    """Generate `training/calibration_sql_genui.txt` containing 200 realistic K-12 Education
    Two-Hop ChatML trajectories for `llama-imatrix` quantization calibration.
    """
    from data_engine import compute_result_summary
    from model_inference import synthesize_semantic_hop2_ui
    from prompts import append_tool_turn, build_two_hop_prompt, get_all_few_shot_examples

    conn = duckdb.connect(":memory:")
    seed_all_warehouses(conn)
    schema = load_unified_schema()

    seed_pairs: list[tuple[str, str]] = []
    for ex in get_all_few_shot_examples():
        seed_pairs.append((ex["question"], ex["sql"].strip().rstrip(";")))
    for item in K12_EXTRA_HOLDOUT_ITEMS:
        seed_pairs.append((item["question"], item["gold_sql"].strip().rstrip(";")))

    extra_questions = [
        (
            f"What is the average attendance rate and GPA for grade {g} students in {yr}?",
            f"SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate, ROUND(AVG(ar.gpa_points), 2) AS avg_gpa FROM main_core.dim_students s JOIN main_core.fact_attendance a ON s.student_id_hash = a.student_id_hash AND s.academic_year = a.academic_year JOIN main_core.fact_academic_records ar ON s.student_id_hash = ar.student_id_hash AND s.academic_year = ar.school_year WHERE s.grade_level = {g} AND s.academic_year = '{yr}'",
        )
        for g in range(1, 13)
        for yr in ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    ]
    extra_cde = [
        (
            f"Show chronic absenteeism rate and suspension rate by school for subgroup {rc} in {yr}",
            f"SELECT school_name, ca_chronic_absent_rate_pct, su_suspension_rate_pct FROM main_analytics.mart_cde_school_accountability WHERE academic_year = '{yr}' AND reporting_category = '{rc}' AND aggregate_level = 'S' ORDER BY ca_chronic_absent_rate_pct DESC",
        )
        for rc in ["TA", "RH", "RB", "RA", "RW", "SE", "EL", "SWD", "HOM", "FOS", "GM", "GF"]
        for yr in ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    ]
    extra_school_queries = [
        (
            f"Show student count, average attendance rate, and average GPA for {sid} vs other schools in {yr}",
            f"SELECT s.school_id, COUNT(DISTINCT s.student_id_hash) AS student_count, ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate, ROUND(AVG(ar.gpa_points), 2) AS avg_gpa FROM main_core.dim_students s JOIN main_core.fact_attendance a ON s.student_id_hash = a.student_id_hash AND s.academic_year = a.academic_year JOIN main_core.fact_academic_records ar ON s.student_id_hash = ar.student_id_hash AND s.academic_year = ar.school_year WHERE s.academic_year = '{yr}' GROUP BY s.school_id ORDER BY avg_gpa DESC",
        )
        for sid, *_ in SCHOOLS
        for yr in ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    ]
    extra_disc_queries = [
        (
            f"How many {inc} incidents and total suspension days occurred by school in {yr}?",
            f"SELECT school_id, COUNT(*) AS incident_count, SUM(suspension_days) AS total_suspension_days FROM main_core.fact_discipline WHERE academic_year = '{yr}' AND incident_type = '{inc}' GROUP BY school_id ORDER BY incident_count DESC",
        )
        for inc, _, _ in INCIDENT_TYPES
        for yr in ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    ]
    extra_equity_queries = [
        (
            f"Compare average attendance rate, suspension percentage, and average GPA for {race} students in equity_by_race",
            f"SELECT primary_race, student_count, avg_attendance_rate, pct_suspended, avg_gpa, pct_high_risk FROM main_analytics.equity_by_race WHERE primary_race = '{race}'",
        )
        for race, _, _ in RACES
    ]

    all_candidates = (
        seed_pairs
        + extra_questions
        + extra_cde
        + extra_school_queries
        + extra_disc_queries
        + extra_equity_queries
    )
    blocks: list[str] = []

    for idx, (question, sql) in enumerate(all_candidates):
        if len(blocks) >= n_samples:
            break
        try:
            pruned = select_training_tables_with_distractors(question, sql, schema, k=5, seed=idx)
            pruned_ddl = format_pruned_ddl(pruned)
            _, _, summary = compute_result_summary(conn, sql, query_id=f"q_cal_{idx:03d}")
            hop1_call = json.dumps(
                {
                    "tool": "execute_duckdb_query",
                    "arguments": {
                        "explanation": f"Query K-12 education warehouse tables to answer: {question}",
                        "sql": sql,
                    },
                },
                separators=(",", ":"),
            )
            hop2_dict = synthesize_semantic_hop2_ui(question, summary)
            hop2_call = json.dumps(hop2_dict, separators=(",", ":"))

            prompt_hop1 = build_two_hop_prompt(question, pruned_ddl)
            full_chat = (
                append_tool_turn(prompt_hop1, hop1_call, summary) + hop2_call + "<|im_end|>\n"
            )
            blocks.append(full_chat)
        except Exception:
            continue

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(blocks), encoding="utf-8")
    conn.close()
    return len(blocks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed K-12 warehouse and build calibration/holdout corpora"
    )
    parser.add_argument(
        "--enrich-local",
        action="store_true",
        help="Enrich oss_framework/data/analytics.duckdb with multi-year K-12 cohorts",
    )
    parser.add_argument(
        "--build-corpora",
        action="store_true",
        help="Generate training/calibration_sql_genui.txt and nl_query/eval_two_hop_holdout.jsonl",
    )
    args = parser.parse_args()

    if args.enrich_local:
        db_file = PROJECT_ROOT / "oss_framework" / "data" / "analytics.duckdb"
        print(f"Enriching local warehouse: {db_file}")
        enrich_existing_warehouse(db_file)
        print("Done enriching local warehouse.")

    if args.build_corpora:
        holdout_path = PROJECT_ROOT / "nl_query" / "eval_two_hop_holdout.jsonl"
        n_holdout = generate_two_hop_holdout(holdout_path)
        print(f"Generated {n_holdout} holdout items -> {holdout_path}")

        cal_path = PROJECT_ROOT / "training" / "calibration_sql_genui.txt"
        n_cal = generate_calibration_corpus(cal_path, n_samples=200)
        print(f"Generated {n_cal} calibration trajectories -> {cal_path}")
