"""
pytest configuration and fixtures for oss_framework tests
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_students_df():
    """Sample students DataFrame for testing"""
    return pd.DataFrame(
        {
            "student_id": ["STU001", "STU002", "STU003", "STU004", "STU005"],
            "first_name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "last_name": ["Smith", "Johnson", "Williams", "Brown", "Davis"],
            "date_of_birth": pd.to_datetime(
                ["2008-05-15", "2008-09-22", "2009-01-10", "2008-07-03", "2009-03-18"]
            ),
            "gender": ["F", "M", "M", "F", "F"],
            "grade_level": [9, 10, 9, 11, 10],
            "school_id": ["SCH001", "SCH001", "SCH001", "SCH002", "SCH002"],
            "english_learner": [False, True, False, False, True],
            "economically_disadvantaged": [True, False, True, False, False],
            "special_education": [False, False, True, False, False],
        }
    )


@pytest.fixture
def sample_courses_df():
    """Sample courses DataFrame for testing"""
    return pd.DataFrame(
        {
            "course_id": ["CRS001", "CRS002", "CRS003", "CRS004"],
            "course_code": ["ELA101", "MATH201", "SCI101", "HIST101"],
            "course_name": [
                "English Language Arts",
                "Algebra II",
                "Biology",
                "World History",
            ],
            "subject_area": ["ELA", "Math", "Science", "Social Studies"],
            "grade_level": ["9-10", "10-12", "9-12", "9-12"],
            "school_id": ["SCH001", "SCH001", "SCH002", "SCH002"],
            "teacher_id": ["TCH001", "TCH002", "TCH003", "TCH004"],
            "course_type": ["regular", "honors", "regular", "AP"],
            "credit_value": [1.0, 1.0, 1.0, 1.0],
        }
    )


@pytest.fixture
def sample_enrollment_df(sample_students_df, sample_courses_df):
    """Sample enrollment DataFrame for testing"""
    return pd.DataFrame(
        {
            "enrollment_id": [
                "ENR001",
                "ENR002",
                "ENR003",
                "ENR004",
                "ENR005",
                "ENR006",
            ],
            "student_id": ["STU001", "STU002", "STU001", "STU003", "STU004", "STU005"],
            "course_id": ["CRS001", "CRS001", "CRS002", "CRS003", "CRS004", "CRS002"],
            "school_id": ["SCH001", "SCH001", "SCH001", "SCH002", "SCH002", "SCH001"],
            "term": [
                "Fall2023",
                "Fall2023",
                "Fall2023",
                "Fall2023",
                "Fall2023",
                "Fall2023",
            ],
            "enrollment_date": pd.to_datetime(["2023-08-15"] * 6),
            "enrollment_status": [
                "active",
                "completed",
                "active",
                "active",
                "active",
                "dropped",
            ],
            "final_grade_numeric": [85.5, 92.0, 78.5, 88.0, 95.0, np.nan],
            "final_grade_letter": ["B", "A", "C", "B", "A", np.nan],
            "credits_earned": [1.0, 1.0, 1.0, 1.0, 1.0, 0.0],
            "attendance_days": [180, 175, 160, 190, 185, 120],
            "absence_count": [2, 5, 20, 1, 3, 60],
            "academic_risk_flag": [False, False, True, False, False, True],
            "engagement_flag": [False, False, True, False, False, True],
        }
    )


@pytest.fixture
def sample_engagement_df(sample_students_df, sample_courses_df):
    """Sample engagement events DataFrame for testing"""
    return pd.DataFrame(
        {
            "event_id": ["EVT001", "EVT002", "EVT003", "EVT004", "EVT005"],
            "student_id": ["STU001", "STU001", "STU002", "STU003", "STU001"],
            "course_id": ["CRS001", "CRS001", "CRS001", "CRS002", "CRS003"],
            "event_timestamp": pd.to_datetime(
                [
                    "2023-09-15 09:30:00",
                    "2023-09-15 10:15:00",
                    "2023-09-16 14:45:00",
                    "2023-09-17 11:20:00",
                    "2023-09-18 13:05:00",
                ]
            ),
            "event_type": [
                "page_view",
                "assignment_submit",
                "quiz_attempt",
                "page_view",
                "discussion_post",
            ],
            "duration_seconds": [600, 1800, 900, 300, 450],
            "interaction_depth": ["view", "submit", "interact", "view", "interact"],
            "content_interaction_flag": [False, True, True, False, True],
        }
    )


@pytest.fixture
def sample_attendance_df(sample_students_df):
    """Sample attendance DataFrame for testing"""
    return pd.DataFrame(
        {
            "attendance_id": ["ATT001", "ATT002", "ATT003", "ATT004", "ATT005"],
            "student_id": ["STU001", "STU001", "STU002", "STU003", "STU001"],
            "school_id": ["SCH001", "SCH001", "SCH001", "SCH002", "SCH001"],
            "attendance_date": pd.to_datetime(
                ["2023-09-15", "2023-09-16", "2023-09-15", "2023-09-15", "2023-09-17"]
            ),
            "is_present": [True, True, False, True, True],
            "absence_type": [np.nan, np.nan, "excused", np.nan, np.nan],
            "tardy_flag": [False, False, False, True, False],
            "chronic_absence_flag": [False, False, True, False, False],
        }
    )


@pytest.fixture
def sample_academic_records_df(sample_students_df):
    """Sample academic records DataFrame for testing"""
    return pd.DataFrame(
        {
            "record_id": ["ACD001", "ACD002", "ACD003", "ACD004", "ACD005"],
            "student_id": ["STU001", "STU002", "STU001", "STU003", "STU001"],
            "course_id": ["CRS001", "CRS001", "CRS002", "CRS003", "CRS001"],
            "assignment_name": [
                "Essay 1",
                "Quiz 1",
                "Midterm",
                "Project",
                "Final Exam",
            ],
            "assignment_type": ["homework", "quiz", "exam", "project", "exam"],
            "points_earned": [45.0, 18.0, 78.0, 95.0, 88.0],
            "points_possible": [50.0, 20.0, 100.0, 100.0, 100.0],
            "assignment_grade_percent": [90.0, 90.0, 78.0, 95.0, 88.0],
            "assignment_grade_letter": ["A", "A", "C", "A", "B"],
            "submission_status": [
                "submitted",
                "submitted",
                "submitted",
                "submitted",
                "submitted",
            ],
            "on_time_flag": [True, True, False, True, True],
            "mastery_level": [
                "proficient",
                "proficient",
                "developing",
                "advanced",
                "proficient",
            ],
        }
    )


@pytest.fixture
def metadata_manager():
    """MetadataManager fixture for testing"""
    from oss_framework import MetadataManager

    metadata_path = Path(__file__).parent.parent / "metadata" / "metadata_combined.csv"
    return MetadataManager(str(metadata_path))


@pytest.fixture
def data_transformer(metadata_manager):
    """DataTransformer fixture with metadata"""
    from oss_framework import DataTransformer

    return DataTransformer(metadata_manager)


@pytest.fixture
def batch_processor(metadata_manager):
    """BatchProcessor fixture with metadata"""
    from oss_framework import BatchProcessor

    return BatchProcessor(metadata_manager)


@pytest.fixture
def pseudonymizer(metadata_manager):
    """Pseudonymizer fixture with metadata"""
    from oss_framework import Pseudonymizer

    return Pseudonymizer(metadata_manager)
