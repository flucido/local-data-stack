"""Education-specific validation tests"""

import pytest
import pandas as pd
import numpy as np


@pytest.mark.education
class TestEducationMetrics:
    """Tests for education-specific metrics and calculations"""

    def test_gpa_calculation(self):
        """Validate GPA calculation from enrollment grades"""
        grades = {
            "course": ["ELA", "Math", "Science", "History"],
            "grade_letter": ["A", "B", "A", "C"],
            "credits": [1.0, 1.0, 1.0, 1.0],
        }
        df = pd.DataFrame(grades)

        grade_points = {"A": 4.0, "B": 3.0, "C": 2.0}
        df["grade_points"] = df["grade_letter"].map(grade_points)

        weighted_sum = (df["grade_points"] * df["credits"]).sum()
        total_credits = df["credits"].sum()
        gpa = weighted_sum / total_credits

        assert 2.5 < gpa < 4.0
        assert gpa == pytest.approx(3.25, rel=0.01)

    def test_attendance_rate_calculation(self, sample_enrollment_df):
        """Validate attendance rate calculation"""
        df = sample_enrollment_df.copy()
        df["attendance_rate"] = (
            df["attendance_days"] / (df["attendance_days"] + df["absence_count"]) * 100
        )

        assert (df["attendance_rate"] >= 0).all()
        assert (df["attendance_rate"] <= 100).all()

    def test_chronic_absenteeism_flag(self):
        """Test chronic absenteeism identification"""
        students = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003"],
                "total_days": [180, 180, 180],
                "absence_count": [18, 5, 2],
            }
        )

        students["attendance_rate"] = (
            students["total_days"]
            / (students["total_days"] + students["absence_count"])
            * 100
        )
        students["chronic_absence"] = students["attendance_rate"] < 90

        assert students.loc[0, "chronic_absence"] == True
        assert students.loc[1, "chronic_absence"] == False
        assert students.loc[2, "chronic_absence"] == False

    def test_academic_risk_flag(self):
        """Test academic risk identification"""
        students = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003"],
                "gpa": [3.8, 2.0, 1.5],
                "attendance_rate": [95, 75, 80],
                "missing_assignments": [0, 3, 8],
            }
        )

        students["at_risk"] = (
            (students["gpa"] < 2.0)
            | (students["attendance_rate"] < 90)
            | (students["missing_assignments"] > 2)
        )

        assert students.loc[0, "at_risk"] == False
        assert students.loc[1, "at_risk"] == True
        assert students.loc[2, "at_risk"] == True

    def test_engagement_categories(self, sample_engagement_df):
        """Test categorizing student engagement levels"""
        df = sample_engagement_df.copy()
        engagement = (
            df.groupby("student_id")
            .agg({"event_id": "count", "duration_seconds": "sum"})
            .reset_index()
        )
        engagement.columns = ["student_id", "event_count", "total_time"]

        engagement["engagement_level"] = pd.cut(
            engagement["event_count"],
            bins=[0, 2, 5, 10, np.inf],
            labels=["Low", "Medium", "High", "Very High"],
        )

        assert len(engagement) > 0
        assert engagement["engagement_level"].isnull().sum() == 0


@pytest.mark.education
class TestStudentOutcomesPrediction:
    """Tests for predicting student outcomes"""

    def test_completion_likelihood_model(self):
        """Test factors predicting course completion"""
        students = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003", "STU004"],
                "prior_gpa": [3.5, 2.5, 3.0, 1.8],
                "attendance_rate": [95, 80, 90, 60],
                "assignment_submission_rate": [1.0, 0.8, 0.9, 0.3],
                "course_completed": [True, True, True, False],
            }
        )

        completion_factors = students[
            (students["attendance_rate"] >= 85)
            & (students["assignment_submission_rate"] >= 0.8)
        ]

        assert len(completion_factors) >= 2

    def test_grade_prediction_factors(self):
        """Test factors predicting final grades"""
        data = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003"],
                "homework_average": [90, 75, 85],
                "quiz_average": [88, 70, 82],
                "engagement_score": [95, 60, 80],
                "final_grade": [88, 72, 83],
            }
        )

        correlation_engagement = (
            data[["engagement_score", "final_grade"]].corr().iloc[0, 1]
        )

        assert correlation_engagement > 0

    def test_dropout_risk_factors(self):
        """Test early warning system for at-risk students"""
        students = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003"],
                "gpa": [3.5, 1.8, 2.5],
                "attendance_rate": [95, 70, 85],
                "behavior_incidents": [0, 3, 1],
                "failed_courses": [0, 2, 0],
            }
        )

        high_risk = students[
            (students["gpa"] < 2.0)
            | (students["attendance_rate"] < 80)
            | (students["behavior_incidents"] > 2)
            | (students["failed_courses"] > 0)
        ]

        assert len(high_risk) == 2


@pytest.mark.education
class TestDataIntegrity:
    """Tests for education data integrity"""

    def test_enrollment_consistency(self, sample_students_df, sample_enrollment_df):
        """Validate enrollment records match student data"""
        enrolled_students = set(sample_enrollment_df["student_id"].unique())
        all_students = set(sample_students_df["student_id"].unique())

        assert enrolled_students.issubset(all_students)

    def test_grade_scale_validity(self):
        """Validate grades are within acceptable ranges"""
        grades = pd.DataFrame(
            {"assignment": ["A1", "A2", "A3", "A4"], "grade_percent": [95, 87, 102, 75]}
        )

        invalid_grades = grades[
            (grades["grade_percent"] < 0) | (grades["grade_percent"] > 100)
        ]

        assert len(invalid_grades) == 1

    def test_credit_accumulation(self):
        """Validate credit calculations"""
        student = pd.DataFrame(
            {
                "course": ["ELA", "Math", "Science", "History"],
                "grade_letter": ["A", "B", "C", "A"],
                "credits_attempted": [1.0, 1.0, 0.5, 1.0],
            }
        )

        passing_grades = ["A", "B", "C", "D"]
        student["credits_earned"] = student.apply(
            lambda row: row["credits_attempted"]
            if row["grade_letter"] in passing_grades
            else 0,
            axis=1,
        )

        total_credits_earned = student["credits_earned"].sum()
        total_credits_attempted = student["credits_attempted"].sum()

        assert total_credits_earned == 3.5
        assert total_credits_attempted == 3.5

    def test_temporal_consistency(self):
        """Validate dates are in correct order"""
        events = pd.DataFrame(
            {
                "event_id": ["E1", "E2", "E3"],
                "enrollment_date": pd.to_datetime(
                    ["2023-08-15", "2023-08-20", "2023-08-18"]
                ),
                "completion_date": pd.to_datetime(
                    ["2023-12-15", "2023-12-10", "2023-12-20"]
                ),
            }
        )

        for _, row in events.iterrows():
            if pd.notna(row["completion_date"]):
                assert row["completion_date"] >= row["enrollment_date"]


@pytest.mark.education
class TestCohortAnalysis:
    """Tests for cohort-based education analytics"""

    def test_cohort_graduation_rate(self):
        """Calculate graduation rates by cohort"""
        cohorts = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003", "STU004"],
                "cohort_year": [2020, 2020, 2021, 2021],
                "graduated": [True, True, False, True],
            }
        )

        graduation_2020 = cohorts[cohorts["cohort_year"] == 2020]["graduated"].mean()
        graduation_2021 = cohorts[cohorts["cohort_year"] == 2021]["graduated"].mean()

        assert 0 <= graduation_2020 <= 1
        assert 0 <= graduation_2021 <= 1
        assert graduation_2020 == 1.0
        assert graduation_2021 == 0.5

    def test_subgroup_achievement_gap(self):
        """Identify achievement gaps across subgroups"""
        students = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", "STU003", "STU004"],
                "english_learner": [True, False, True, False],
                "gpa": [2.5, 3.8, 2.2, 3.9],
            }
        )

        el_avg_gpa = students[students["english_learner"]]["gpa"].mean()
        non_el_avg_gpa = students[~students["english_learner"]]["gpa"].mean()
        gap = non_el_avg_gpa - el_avg_gpa

        assert gap > 0

    def test_equity_indicators(self):
        """Test equity indicators across demographics"""
        data = pd.DataFrame(
            {
                "student_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
                "economically_disadvantaged": [True, False, True, False, True, False],
                "advanced_placement": [False, True, False, True, False, True],
            }
        )

        disadvantaged_ap_rate = data[data["economically_disadvantaged"]][
            "advanced_placement"
        ].sum() / len(data[data["economically_disadvantaged"]])

        privileged_ap_rate = data[~data["economically_disadvantaged"]][
            "advanced_placement"
        ].sum() / len(data[~data["economically_disadvantaged"]])

        assert disadvantaged_ap_rate < privileged_ap_rate
