import sys
import os

# Ensure we can import from src when running this script directly from repo root
sys.path.append(os.getcwd())

from src.db.connection import DuckDBConnection

def run_analytics() -> None:
    """
    Executes sample analytics queries against the Delta Lake using DuckDB.
    """
    # Get the singleton connection (initializes DuckDB and loads Delta extension)
    db = DuckDBConnection()
    conn = db.get_connection()

    print("Running Analytics Queries on DuckLake...")

    # Define paths to Delta tables
    base_path = "data/delta"
    staff_path = os.path.join(base_path, "staff")
    students_path = os.path.join(base_path, "students")
    grades_path = os.path.join(base_path, "grades")

    # Query 1: Count Staff by Department
    print("\n--- Staff Count by Department ---")
    query_1 = f"""
    SELECT department, COUNT(*) as count
    FROM delta_scan('{staff_path}')
    GROUP BY department
    ORDER BY count DESC
    """
    try:
        print(conn.execute(query_1).df())
    except Exception as e:
        print(f"Error executing Query 1: {e}")

    # Query 2: Student Enrollment Count
    print("\n--- Student Enrollment Count ---")
    query_2 = f"""
    SELECT grade, COUNT(*) as count
    FROM delta_scan('{students_path}')
    GROUP BY grade
    ORDER BY grade
    """
    try:
        print(conn.execute(query_2).df())
    except Exception as e:
        print(f"Error executing Query 2: {e}")

    # Query 3: Average GPA by Grade
    # Demonstrates joining two Delta tables
    print("\n--- Average GPA by Grade ---")
    query_3 = f"""
    WITH grade_points AS (
        SELECT
            student_id,
            CASE mark
                WHEN 'A' THEN 4.0
                WHEN 'B' THEN 3.0
                WHEN 'C' THEN 2.0
                WHEN 'D' THEN 1.0
                ELSE 0.0
            END as points
        FROM delta_scan('{grades_path}')
    ),
    student_gpa AS (
        SELECT student_id, AVG(points) as gpa
        FROM grade_points
        GROUP BY student_id
    )
    SELECT
        s.grade,
        AVG(g.gpa) as avg_gpa
    FROM delta_scan('{students_path}') s
    JOIN student_gpa g ON s.student_id = g.student_id
    GROUP BY s.grade
    ORDER BY s.grade
    """
    try:
        print(conn.execute(query_3).df())
    except Exception as e:
        print(f"Error executing Query 3: {e}")

if __name__ == "__main__":
    run_analytics()
