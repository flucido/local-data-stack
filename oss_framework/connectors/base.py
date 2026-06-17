"""Abstract SISConnector interface and canonical data schemas.

Every Student Information System connector implements this ABC so that
pipelines operate against a vendor-neutral contract.  Column mappings
translate vendor-specific names into the canonical schema defined here.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical column schemas — the target shape every connector normalizes into.
# These are Python type hints for documentation; the actual normalization
# happens in each connector's column_mapping + transform step.
# ---------------------------------------------------------------------------

CANONICAL_STUDENT_COLUMNS = {
    "student_id": str,
    "first_name": str,
    "last_name": str,
    "date_of_birth": "date",
    "gender": str,
    "race_ethnicity": str,
    "grade_level": int,
    "school_id": str,
    "academic_year": str,
    "ell_status": str,
    "special_education_flag": bool,
    "free_reduced_lunch_flag": bool,
    "homeless_flag": bool,
    "foster_care_flag": bool,
    "section_504_flag": bool,
    "home_language": str,
    "enrollment_date": "date",
    "withdrawal_date": "date",
    "created_at": "datetime",
    "updated_at": "datetime",
}

CANONICAL_ATTENDANCE_COLUMNS = {
    "student_id": str,
    "school_id": str,
    "academic_year": str,
    "attendance_date": "date",
    "attendance_status": str,
    "absence_reason": str,
    "present_flag": bool,
    "absent_flag": bool,
    "tardy_flag": bool,
    "excused_flag": bool,
    "unexcused_flag": bool,
    "created_at": "datetime",
}

CANONICAL_GRADES_COLUMNS = {
    "student_id": str,
    "school_id": str,
    "course_id": str,
    "section_id": str,
    "teacher_id": str,
    "grade": str,
    "score": float,
    "term": str,
    "school_year": str,
    "created_at": "datetime",
}

CANONICAL_DISCIPLINE_COLUMNS = {
    "student_id": str,
    "school_id": str,
    "incident_id": str,
    "incident_date": "date",
    "incident_type": str,
    "severity": str,
    "resolution": str,
    "suspension_days": int,
    "created_at": "datetime",
}

CANONICAL_ENROLLMENT_COLUMNS = {
    "student_id": str,
    "school_id": str,
    "school_year": str,
    "enrollment_date": "date",
    "withdrawal_date": "date",
    "grade_level": int,
    "enrollment_status": str,
    "created_at": "datetime",
}


class SISConnector(ABC):
    """Abstract interface for any Student Information System connector.

    Each concrete implementation must provide:
      - The five data-extraction methods below.
      - A ``column_mapping`` dict (vendor column → canonical column).
      - A ``connector_name`` class attribute for introspection.

    Pipelines call these methods directly; the connector is responsible for
    normalizing column names and data types to the canonical schemas above.
    """

    connector_name: str = "base"

    @property
    @abstractmethod
    def column_mapping(self) -> Dict[str, Dict[str, str]]:
        """Return per-domain column mappings.

        Returns:
            Dict of domain_name → {vendor_column: canonical_column}.
            Domains: students, attendance, grades, discipline, enrollment.
        """
        ...

    @abstractmethod
    def get_students(self, school_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return student records with canonical column names."""
        ...

    @abstractmethod
    def get_attendance(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Return attendance records with canonical column names."""
        ...

    @abstractmethod
    def get_grades(self) -> List[Dict[str, Any]]:
        """Return grade / academic records with canonical column names."""
        ...

    @abstractmethod
    def get_discipline(self) -> List[Dict[str, Any]]:
        """Return discipline incident records with canonical column names."""
        ...

    @abstractmethod
    def get_enrollment(self) -> List[Dict[str, Any]]:
        """Return enrollment records with canonical column names."""
        ...
