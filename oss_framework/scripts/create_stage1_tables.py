"""Create Stage 1 landing zone tables"""

import duckdb
import logging

from config import DUCKDB_DATABASE_PATH

logger = logging.getLogger(__name__)


class Stage1Initializer:
    """Initialize Stage 1 landing zone tables"""

    def __init__(self):
        self.con = duckdb.connect(DUCKDB_DATABASE_PATH)
        self.tables_created = {}

    def create_all_stage1_tables(self):
        """Create all Stage 1 raw landing tables"""
        try:
            # Create raw_students table
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS raw_students (
                    student_id VARCHAR,
                    first_name VARCHAR,
                    last_name VARCHAR,
                    date_of_birth DATE,
                    gender VARCHAR,
                    ethnicity VARCHAR,
                    free_reduced_lunch BOOLEAN,
                    ell_status VARCHAR,
                    special_education BOOLEAN,
                    section_504 BOOLEAN,
                    homeless BOOLEAN,
                    foster_care BOOLEAN,
                    school_id VARCHAR,
                    grade_level INTEGER,
                    enrollment_date DATE,
                    withdrawal_date DATE,
                    home_language VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.tables_created["raw_students"] = "OK"
            logger.info("Created raw_students table")

            # Create raw_attendance table
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS raw_attendance (
                    attendance_id VARCHAR,
                    student_id VARCHAR,
                    school_id VARCHAR,
                    attendance_date DATE,
                    attendance_status VARCHAR,
                    absence_reason VARCHAR,
                    present_flag BOOLEAN,
                    absent_flag BOOLEAN,
                    tardy_flag BOOLEAN,
                    excused_flag BOOLEAN,
                    unexcused_flag BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.tables_created["raw_attendance"] = "OK"
            logger.info("Created raw_attendance table")

            # Create raw_academic_records table
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS raw_academic_records (
                    record_id VARCHAR,
                    student_id VARCHAR,
                    school_id VARCHAR,
                    course_id VARCHAR,
                    section_id VARCHAR,
                    teacher_id VARCHAR,
                    grade VARCHAR,
                    score DECIMAL(5,2),
                    term VARCHAR,
                    school_year VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.tables_created["raw_academic_records"] = "OK"
            logger.info("Created raw_academic_records table")

            # Create raw_discipline table
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS raw_discipline (
                    incident_id VARCHAR,
                    student_id VARCHAR,
                    school_id VARCHAR,
                    incident_date DATE,
                    incident_type VARCHAR,
                    severity VARCHAR,
                    resolution VARCHAR,
                    suspension_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.tables_created["raw_discipline"] = "OK"
            logger.info("Created raw_discipline table")

            # Create raw_enrollment table
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS raw_enrollment (
                    enrollment_id VARCHAR,
                    student_id VARCHAR,
                    school_id VARCHAR,
                    school_year VARCHAR,
                    enrollment_date DATE,
                    withdrawal_date DATE,
                    grade_level INTEGER,
                    enrollment_status VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.tables_created["raw_enrollment"] = "OK"
            logger.info("Created raw_enrollment table")

        except Exception as e:
            logger.error(f"Error creating Stage 1 tables: {str(e)}")
            raise

    def close(self):
        """Close database connection"""
        self.con.close()


if __name__ == "__main__":
    init = Stage1Initializer()
    init.create_all_stage1_tables()
    print(f"✅ Created {len(init.tables_created)} tables")
    init.close()
