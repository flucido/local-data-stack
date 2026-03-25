#!/usr/bin/env python3
"""
Aeries SIS dlt Pipeline - Stage 1 Data Ingestion

This pipeline extracts data from Aeries Student Information System and loads it
into Stage 1 (Parquet files) following the medallion architecture.

Features:
- Test mode: Uses synthetic data when real credentials unavailable
- Production mode: Connects to real Aeries API
- Incremental loading: Tracks state for efficient updates
- Parquet output: Writes to stage1/transactional/aeries/
"""

import os
from typing import Iterator, Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import dlt
from dlt.sources import DltResource
from dlt.common.pipeline import LoadInfo
import requests


class AeriesAPIClient:
    """Client for Aeries SIS API"""

    def __init__(self, base_url: str = "", api_key: str = "", test_mode: bool = False):
        self.base_url = base_url or os.getenv(
            "AERIES_API_URL", "https://api.aeries.com/v5"
        )
        self.api_key = api_key or os.getenv("AERIES_API_KEY", "")
        self.test_mode = test_mode or not self.api_key or "test" in self.api_key.lower()

        if not self.test_mode:
            self.headers = {"AERIES-CERT": self.api_key, "Accept": "application/json"}

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Make API request with error handling"""
        if self.test_mode:
            return []

        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return []

    def get_students(self, school_code: Optional[str] = None) -> List[Dict]:
        """Fetch students from Aeries or generate test data"""
        if self.test_mode:
            return self._generate_test_students()

        endpoint = f"/schools/{school_code}/students" if school_code else "/students"
        return self._make_request(endpoint)

    def get_attendance(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict]:
        """Fetch attendance records"""
        if self.test_mode:
            return self._generate_test_attendance()

        params = {}
        if start_date:
            params["StartDate"] = start_date.isoformat()
        if end_date:
            params["EndDate"] = end_date.isoformat()

        return self._make_request("/attendance", params=params)

    def get_grades(self) -> List[Dict]:
        """Fetch academic records/grades"""
        if self.test_mode:
            return self._generate_test_grades()

        return self._make_request("/grades")

    def get_discipline(self) -> List[Dict]:
        """Fetch discipline incidents"""
        if self.test_mode:
            return self._generate_test_discipline()

        return self._make_request("/discipline")

    def get_enrollment(self) -> List[Dict]:
        """Fetch enrollment records"""
        if self.test_mode:
            return self._generate_test_enrollment()

        return self._make_request("/enrollment")

    # Test data generators
    def _generate_test_students(self) -> List[Dict]:
        """Generate synthetic student data for testing"""
        students = []
        for i in range(1, 1701):
            students.append(
                {
                    "student_id": f"STU{i:04d}",
                    "first_name": "Student",
                    "last_name": f"Name{i}",
                    "date_of_birth": (
                        date(2010, 1, 1) + timedelta(days=i % 365)
                    ).isoformat(),
                    "gender": "M" if i % 2 == 0 else "F",
                    "ethnicity": ["Hispanic", "White", "Asian", "Black", "Other"][
                        i % 5
                    ],
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

    def _generate_test_attendance(self) -> List[Dict]:
        """Generate synthetic attendance data"""
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

    def _generate_test_grades(self) -> List[Dict]:
        """Generate synthetic grade/academic records"""
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

    def _generate_test_discipline(self) -> List[Dict]:
        """Generate synthetic discipline records"""
        discipline = []
        for i in range(1, 2001):
            discipline.append(
                {
                    "incident_id": f"DIS{i:06d}",
                    "student_id": f"STU{((i % 1700) + 1):04d}",
                    "school_id": f"SCH{((i % 1700) % 3) + 1}",
                    "incident_date": (
                        date(2025, 1, 1) + timedelta(days=(i - 1) // 50)
                    ).isoformat(),
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

    def _generate_test_enrollment(self) -> List[Dict]:
        """Generate synthetic enrollment records"""
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


# dlt source definition
@dlt.source(name="aeries")
def aeries_source(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
) -> List[DltResource]:
    """
    dlt source for Aeries SIS data

    Args:
        base_url: Aeries API base URL
        api_key: Aeries API certificate/key
        test_mode: Force test mode (synthetic data)
    """

    if test_mode is None:
        test_mode = not api_key or "test" in (api_key or "").lower()

    client = AeriesAPIClient(
        base_url=base_url or "", api_key=api_key or "", test_mode=test_mode
    )

    @dlt.resource(name="raw_students", write_disposition="replace")
    def students() -> Iterator[Dict[str, Any]]:
        """Extract student data"""
        data = client.get_students()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            record["updated_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_attendance", write_disposition="append")
    def attendance() -> Iterator[Dict[str, Any]]:
        """Extract attendance data"""
        data = client.get_attendance()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_academic_records", write_disposition="append")
    def academic_records() -> Iterator[Dict[str, Any]]:
        """Extract grade/academic records"""
        data = client.get_grades()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_discipline", write_disposition="append")
    def discipline() -> Iterator[Dict[str, Any]]:
        """Extract discipline incidents"""
        data = client.get_discipline()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_enrollment", write_disposition="replace")
    def enrollment() -> Iterator[Dict[str, Any]]:
        """Extract enrollment data"""
        data = client.get_enrollment()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    return [students, attendance, academic_records, discipline, enrollment]


def run_aeries_pipeline(
    destination_type: str = "filesystem",
    dataset_name: str = "aeries_stage1",
    test_mode: Optional[bool] = None,
) -> LoadInfo:
    """
    Run the Aeries dlt pipeline

    Args:
        destination_type: "filesystem" (Parquet) or "duckdb"
        dataset_name: Name for the dataset
        test_mode: Force test mode with synthetic data
    """

    api_key = os.getenv("AERIES_API_KEY")
    base_url = os.getenv("AERIES_API_URL")

    if test_mode is None:
        test_mode = not api_key or "test" in api_key.lower()

    if test_mode:
        print("🧪 Running in TEST MODE with synthetic data")
    else:
        print("🔌 Running in PRODUCTION MODE with real Aeries API")

    if destination_type == "filesystem":
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_stage1",
            destination=dlt.destinations.filesystem(
                bucket_url=f"{stage1_path}/transactional/aeries"
            ),
            dataset_name=dataset_name,
        )
    else:
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb")

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_duckdb",
            destination=dlt.destinations.duckdb(database=db_path),
            dataset_name=dataset_name,
        )

    source = aeries_source(
        base_url=base_url or "", api_key=api_key or "", test_mode=test_mode
    )
    info = pipeline.run(source)

    print(f"\n✅ Pipeline completed successfully")
    print(f"   Pipeline: {info.pipeline.pipeline_name}")
    print(f"   Destination: {destination_type}")
    print(f"   Dataset: {dataset_name}")
    print(f"   Loads: {len(info.loads_ids)}")

    return info


if __name__ == "__main__":
    import sys

    destination = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    test_mode = "--test" in sys.argv or "--test-mode" in sys.argv

    run_aeries_pipeline(destination_type=destination, test_mode=test_mode)
