"""Aeries SIS connector.

Implements the SISConnector interface for Aeries Student Information System.
Supports both real API access (AERIES-CERT header auth) and synthetic test data.
"""

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from oss_framework.connectors.base import SISConnector
from oss_framework.connectors.mappings.aeries_to_canonical import AERIES_COLUMN_MAPPING


class AeriesConnector(SISConnector):
    """Connector for Aeries SIS — API or synthetic test mode."""

    connector_name = "aeries"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        test_mode: bool = False,
    ):
        self.base_url = base_url or os.getenv(
            "SIS_API_URL", os.getenv("AERIES_API_URL", "https://api.aeries.com/v5")
        )
        self.api_key = api_key or os.getenv("SIS_API_KEY", os.getenv("AERIES_API_KEY", ""))
        self.test_mode = test_mode or not self.api_key

        if not self.test_mode:
            self.headers = {
                "AERIES-CERT": self.api_key,
                "Accept": "application/json",
            }

    # ------------------------------------------------------------------
    # SISConnector interface
    # ------------------------------------------------------------------

    @property
    def column_mapping(self) -> Dict[str, Dict[str, str]]:
        """Return Aeries → canonical column mappings per domain."""
        return AERIES_COLUMN_MAPPING

    def get_students(self, school_code: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.test_mode:
            return self._generate_test_students()
        endpoint = f"/schools/{school_code}/students" if school_code else "/students"
        return self._make_request(endpoint)

    def get_attendance(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        if self.test_mode:
            return self._generate_test_attendance()
        params: Dict[str, str] = {}
        if start_date:
            params["StartDate"] = start_date.isoformat()
        if end_date:
            params["EndDate"] = end_date.isoformat()
        return self._make_request("/attendance", params=params)

    def get_grades(self) -> List[Dict[str, Any]]:
        if self.test_mode:
            return self._generate_test_grades()
        return self._make_request("/grades")

    def get_discipline(self) -> List[Dict[str, Any]]:
        if self.test_mode:
            return self._generate_test_discipline()
        return self._make_request("/discipline")

    def get_enrollment(self) -> List[Dict[str, Any]]:
        if self.test_mode:
            return self._generate_test_enrollment()
        return self._make_request("/enrollment")

    # ------------------------------------------------------------------
    # Internal: API helpers
    # ------------------------------------------------------------------

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        if self.test_mode:
            return []
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return []

    # ------------------------------------------------------------------
    # Synthetic test-data generators (canonical column names)
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_test_students() -> List[Dict[str, Any]]:
        students = []
        for i in range(1, 1701):
            students.append(
                {
                    "student_id": f"STU{i:04d}",
                    "first_name": "Student",
                    "last_name": f"Name{i}",
                    "date_of_birth": (date(2010, 1, 1) + timedelta(days=i % 365)).isoformat(),
                    "gender": "M" if i % 2 == 0 else "F",
                    "ethnicity": ["Hispanic", "White", "Asian", "Black", "Other"][i % 5],
                    "free_reduced_lunch": i % 4 == 0,
                    "ell_status": i % 10 == 0,
                    "special_education": i % 20 == 0,
                    "section_504": i % 25 == 0,
                    "homeless": i % 50 == 0,
                    "foster_care": i % 60 == 0,
                    "school_id": f"SCH{(i % 3) + 1}",
                    "grade_level": (i % 12) + 1,
                    "enrollment_date": "2024-08-01",
                    "withdrawal_date": None,
                    "home_language": "SPANISH" if i % 7 == 0 else "ENGLISH",
                }
            )
        return students

    @staticmethod
    def _generate_test_attendance() -> List[Dict[str, Any]]:
        attendance = []
        for i in range(1, 45001):
            day_offset = (i - 1) // 1700
            attendance.append(
                {
                    "attendance_id": f"ATT{i:08d}",
                    "student_id": f"STU{((i % 1700) + 1):04d}",
                    "school_id": f"SCH{((i % 1700) % 3) + 1}",
                    "attendance_date": (
                        date(2025, 1, 1) + timedelta(days=day_offset % 180)
                    ).isoformat(),
                    "attendance_status": "Absent" if i % 20 == 0 else "Present",
                    "absence_reason": "SICK" if i % 20 == 0 else None,
                    "present_flag": i % 20 != 0,
                    "absent_flag": i % 20 == 0,
                    "tardy_flag": i % 33 == 0,
                    "excused_flag": i % 40 == 0,
                    "unexcused_flag": i % 45 == 0,
                }
            )
        return attendance

    @staticmethod
    def _generate_test_grades() -> List[Dict[str, Any]]:
        grades = []
        for i in range(1, 200001):
            score = 50 + (i % 50)
            grades.append(
                {
                    "record_id": f"GRD{i:08d}",
                    "student_id": f"STU{((i % 1700) + 1):04d}",
                    "school_id": f"SCH{((i % 1700) % 3) + 1}",
                    "course_id": f"CRS{(i % 50) + 1}",
                    "section_id": f"SEC{(i % 100) + 1}",
                    "teacher_id": f"TCH{(i % 25) + 1}",
                    "grade": ["F", "D", "C", "B", "A"][min((i % 100) // 20, 4)],
                    "score": float(score),
                    "term": "Q1",
                    "school_year": "2024-2025",
                }
            )
        return grades

    @staticmethod
    def _generate_test_discipline() -> List[Dict[str, Any]]:
        discipline = []
        for i in range(1, 2001):
            discipline.append(
                {
                    "incident_id": f"DIS{i:06d}",
                    "student_id": f"STU{((i % 1700) + 1):04d}",
                    "school_id": f"SCH{((i % 1700) % 3) + 1}",
                    "incident_date": (date(2025, 1, 1) + timedelta(days=(i - 1) // 50)).isoformat(),
                    "incident_type": [
                        "Tardy",
                        "Behavior",
                        "Class Disruption",
                        "Other",
                        "Other",
                    ][i % 5],
                    "severity": ["Low", "Medium", "High"][i % 3],
                    "resolution": "Parent Contact" if i % 7 == 0 else "Warning",
                    "suspension_days": 1 if i % 11 == 0 else (2 if i % 17 == 0 else 0),
                }
            )
        return discipline

    @staticmethod
    def _generate_test_enrollment() -> List[Dict[str, Any]]:
        enrollment = []
        for i in range(1, 1701):
            enrollment.append(
                {
                    "enrollment_id": f"ENR{i:06d}",
                    "student_id": f"STU{i:04d}",
                    "school_id": f"SCH{(i % 3) + 1}",
                    "school_year": "2024-2025",
                    "enrollment_date": "2024-08-01",
                    "withdrawal_date": None,
                    "grade_level": (i % 12) + 1,
                    "enrollment_status": "ACTIVE",
                }
            )
        return enrollment


def create_connector(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
    **kwargs,
) -> AeriesConnector:
    """Factory for AeriesConnector — called by get_sis_connector()."""
    return AeriesConnector(
        base_url=base_url or "",
        api_key=api_key or "",
        test_mode=test_mode if test_mode is not None else False,
    )
