"""
Visualize the relationship between student attendance rate and GPA using DuckDB.

This script:
1) Connects to DuckDB (loading the Delta Lake extension).
2) Queries Stage 2 Delta tables from the DuckLake architecture for attendance and grades.
3) Renders a density-friendly hexbin chart to surface the correlation between attendance and GPA.
"""

import os
import sys
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

# Ensure imports work when running directly from repo root
sys.path.append(os.getcwd())

from src.db.connection import get_connection


def fetch_attendance_gpa(connection) -> pd.DataFrame:
    """
    Fetch attendance rate and GPA joined on student_id from local Delta tables.

    Reads from local Delta Lake directories in data/stage2/.
    """
    # Use environment variables for stage paths with sensible defaults
    stage2_path = os.getenv('STAGE2_PATH', './data/stage2')
    
    query = f"""
        SELECT a.attendance_rate, g.gpa
        FROM delta_scan('{stage2_path}/ingested/aeries_attendance') a
        JOIN delta_scan('{stage2_path}/ingested/aeries_grades') g
          ON a.student_id = g.student_id
        WHERE a.attendance_rate IS NOT NULL
          AND g.gpa IS NOT NULL
    """
    return connection.execute(query).fetch_df()


def plot_attendance_vs_gpa(df: pd.DataFrame, output_path: Optional[str] = None) -> None:
    """
    Create a hexbin plot to handle large volumes and potential overplotting.
    """
    plt.figure(figsize=(8, 6))
    hb = plt.hexbin(
        df["attendance_rate"],
        df["gpa"],
        gridsize=40,
        cmap="viridis",
        mincnt=1,
    )
    plt.colorbar(hb, label="Student count")
    plt.xlabel("Attendance Rate")
    plt.ylabel("GPA")
    plt.title("Attendance Rate vs GPA")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.xlim(0, 1)
    plt.ylim(0, 4)

    if output_path:
        plt.tight_layout()
        plt.savefig(output_path)
        print(f"Chart saved to {output_path}")
    else:
        plt.show()


def main(output_path: Optional[str] = None) -> None:
    conn = get_connection()
    
    print("Querying attendance and GPA data from local Delta tables...")
    df = fetch_attendance_gpa(conn)
    print(f"Retrieved {len(df)} records.")

    plot_attendance_vs_gpa(df, output_path=output_path)


if __name__ == "__main__":
    main()
