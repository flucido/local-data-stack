"""Ingest data from Aeries API"""

import duckdb
import logging

from config import DUCKDB_DATABASE_PATH

logger = logging.getLogger(__name__)


class AeriesDataIngestor:
    """Ingest data from Aeries API or local test data"""

    def __init__(self):
        self.con = duckdb.connect(DUCKDB_DATABASE_PATH)
        self.results = {}

    def run_full_ingest(self):
        """Run complete data ingestion"""
        try:
            # Insert sample students
            self.con.execute("""
                INSERT INTO raw_students 
                (student_id, first_name, last_name, date_of_birth, gender, ethnicity, school_id, grade_level)
                SELECT 
                    'STU' || LPAD(CAST(id AS VARCHAR), 4, '0'),
                    'Student',
                    'Name' || id,
                    CAST(DATE '2010-01-01' + (INTERVAL '1' DAY) * id AS DATE),
                    CASE WHEN id % 2 = 0 THEN 'M' ELSE 'F' END,
                    CASE id % 5 
                        WHEN 0 THEN 'Hispanic'
                        WHEN 1 THEN 'White'
                        WHEN 2 THEN 'Asian'
                        WHEN 3 THEN 'Black'
                        ELSE 'Other'
                    END,
                    'SCH' || (id % 3 + 1),
                    (id % 12) + 1
                FROM (SELECT * FROM RANGE(1, 1701) AS r(id))
            """)
            student_count = self.con.execute(
                "SELECT COUNT(*) FROM raw_students"
            ).fetchone()[0]
            self.results["students"] = student_count
            logger.info(f"Ingested {student_count} students")

            # Insert sample attendance
            self.con.execute("""
                INSERT INTO raw_attendance
                (attendance_id, student_id, school_id, attendance_date, attendance_status, present_flag)
                SELECT 
                    'ATT' || LPAD(CAST(id AS VARCHAR), 8, '0'),
                    'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0'),
                    'SCH' || ((id % 1700) % 3 + 1),
                    CAST(DATE '2025-01-01' + (INTERVAL '1' DAY) * ((id - 1) / 1700) AS DATE),
                    CASE WHEN id % 20 = 0 THEN 'Absent' ELSE 'Present' END,
                    CASE WHEN id % 20 = 0 THEN false ELSE true END
                FROM (SELECT * FROM RANGE(1, 45001) AS r(id))
            """)
            attendance_count = self.con.execute(
                "SELECT COUNT(*) FROM raw_attendance"
            ).fetchone()[0]
            self.results["attendance"] = attendance_count
            logger.info(f"Ingested {attendance_count} attendance records")

            # Insert sample grades
            self.con.execute("""
                INSERT INTO raw_academic_records
                (record_id, student_id, school_id, course_id, grade, score, term, school_year)
                SELECT 
                    'GRD' || LPAD(CAST(id AS VARCHAR), 8, '0'),
                    'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0'),
                    'SCH' || ((id % 1700) % 3 + 1),
                    'CRS' || ((id % 50) + 1),
                    CASE WHEN id % 100 < 10 THEN 'F' 
                         WHEN id % 100 < 25 THEN 'D'
                         WHEN id % 100 < 50 THEN 'C'
                         WHEN id % 100 < 75 THEN 'B'
                         ELSE 'A' END,
                    CAST(50 + (id % 50) AS DECIMAL(5,2)),
                    'Q1',
                    '2024-2025'
                FROM (SELECT * FROM RANGE(1, 200001) AS r(id))
            """)
            grade_count = self.con.execute(
                "SELECT COUNT(*) FROM raw_academic_records"
            ).fetchone()[0]
            self.results["grades"] = grade_count
            logger.info(f"Ingested {grade_count} grade records")

            # Insert sample discipline
            self.con.execute("""
                INSERT INTO raw_discipline
                (incident_id, student_id, school_id, incident_date, incident_type, severity)
                SELECT 
                    'DIS' || LPAD(CAST(id AS VARCHAR), 6, '0'),
                    'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0'),
                    'SCH' || ((id % 1700) % 3 + 1),
                    CAST(DATE '2025-01-01' + (INTERVAL '1' DAY) * ((id - 1) / 50) AS DATE),
                    CASE id % 5 
                        WHEN 0 THEN 'Tardy'
                        WHEN 1 THEN 'Behavior'
                        WHEN 2 THEN 'Class Disruption'
                        ELSE 'Other'
                    END,
                    CASE id % 3
                        WHEN 0 THEN 'Low'
                        WHEN 1 THEN 'Medium'
                        ELSE 'High'
                    END
                FROM (SELECT * FROM RANGE(1, 2001) AS r(id))
            """)
            discipline_count = self.con.execute(
                "SELECT COUNT(*) FROM raw_discipline"
            ).fetchone()[0]
            self.results["discipline"] = discipline_count
            logger.info(f"Ingested {discipline_count} discipline records")

            # Insert sample enrollment
            self.con.execute("""
                INSERT INTO raw_enrollment
                (enrollment_id, student_id, school_id, school_year, enrollment_date, grade_level)
                SELECT 
                    'ENR' || LPAD(CAST(id AS VARCHAR), 6, '0'),
                    'STU' || LPAD(CAST(id AS VARCHAR), 4, '0'),
                    'SCH' || (id % 3 + 1),
                    '2024-2025',
                    CAST(DATE '2024-08-01' + (INTERVAL '1' DAY) * ((id - 1) / 1700) AS DATE),
                    (id % 12) + 1
                FROM (SELECT * FROM RANGE(1, 1701) AS r(id))
            """)
            enrollment_count = self.con.execute(
                "SELECT COUNT(*) FROM raw_enrollment"
            ).fetchone()[0]
            self.results["enrollment"] = enrollment_count
            logger.info(f"Ingested {enrollment_count} enrollment records")

            return self.results

        except Exception as e:
            logger.error(f"Error ingesting data: {str(e)}")
            raise

    def close(self):
        """Close database connection"""
        self.con.close()


if __name__ == "__main__":
    ingestor = AeriesDataIngestor()
    results = ingestor.run_full_ingest()
    print("✅ Data ingestion complete:")
    for key, count in results.items():
        print(f"  - {key}: {count} records")
    ingestor.close()
