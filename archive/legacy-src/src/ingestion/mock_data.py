import pandas as pd
import numpy as np
import os
import random
from datetime import datetime, timedelta
from deltalake import write_deltalake

# Setup directories
DELTA_PATH = "data/delta"
os.makedirs(DELTA_PATH, exist_ok=True)

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

def generate_mock_data() -> None:
    print("Generating Aeries-Compatible Mock Data (Delta Lake)...")

    # ==========================================
    # 1. Generate Staff (STF)
    # ==========================================
    print("  - Generating Staff (STF)...")
    departments = ["Math", "Science", "English", "History", "Art", "PE", "SpecialEd"]
    staff_data = []
    staff_ids = range(100, 150) # 50 staff members

    for sid in staff_ids:
        dept = np.random.choice(departments)
        staff_data.append({
            "staff_id": sid,
            "first_name": f"StaffFN{sid}",
            "last_name": f"StaffLN{sid}",
            "email": f"staff{sid}@schooldistrict.edu",
            "department": dept,
            "job_class": "Teacher"
        })

    # Add a few counselors
    counselor_ids = range(200, 205)
    for cid in counselor_ids:
        staff_data.append({
            "staff_id": cid,
            "first_name": f"CounselorFN{cid}",
            "last_name": f"CounselorLN{cid}",
            "email": f"counselor{cid}@schooldistrict.edu",
            "department": "Counseling",
            "job_class": "Counselor"
        })

    staff_df = pd.DataFrame(staff_data)
    write_deltalake(os.path.join(DELTA_PATH, "staff"), staff_df, mode="overwrite")

    # ==========================================
    # 2. Generate Courses (CRS)
    # ==========================================
    print("  - Generating Courses (CRS)...")
    courses_data = []

    # Define some core courses
    core_courses = {
        "Math": ["Algebra I", "Geometry", "Algebra II", "Pre-Calculus", "Calculus AB"],
        "Science": ["Biology", "Chemistry", "Physics", "Env Science"],
        "English": ["English 9", "English 10", "English 11", "English 12"],
        "History": ["World History", "US History", "Gov/Econ"],
        "Art": ["Art I", "Ceramics"],
        "PE": ["PE 9", "PE 10"]
    }

    course_catalog = []
    cid_counter = 1000

    for dept, course_list in core_courses.items():
        for name in course_list:
            course_catalog.append({
                "course_id": str(cid_counter),
                "course_title": name,
                "short_title": name[:10],
                "department": dept,
                "credits": 5.0,
                "uc_csu": "Y" if dept in ["Math", "Science", "English", "History", "Art"] else "N",
                "subject_area": dept[0]
            })
            cid_counter += 1

    courses_df = pd.DataFrame(course_catalog)
    write_deltalake(os.path.join(DELTA_PATH, "courses"), courses_df, mode="overwrite")

    # ==========================================
    # 3. Generate Master Schedule (MST) & Sections
    # ==========================================
    print("  - Generating Master Schedule (MST)...")
    mst_data = []
    section_staff_data = []
    section_counter = 5000

    # Create sections for each course
    # Simple logic: 2 sections per course per period for periods 1-6
    periods = ["1", "2", "3", "4", "5", "6"]

    for course in course_catalog:
        # Find teachers for this department
        dept_teachers = [s for s in staff_data if s['department'] == course['department']]
        if not dept_teachers:
            continue

        for period in periods:
            # Create 1-2 sections per period
            num_sections = 1 if "PE" in course['course_title'] else 2

            for _ in range(num_sections):
                teacher = np.random.choice(dept_teachers)

                mst_data.append({
                    "section_id": section_counter,
                    "school_id": 999,
                    "course_id": course['course_id'],
                    "course_title": course['course_title'],
                    "period": period,
                    "room": f"R{np.random.randint(100, 300)}",
                    "semester": "Y",
                    "max_students": 35,
                    "current_enrollment": 0, # Will update later
                    "department": course['department']
                })

                section_staff_data.append({
                    "section_id": section_counter,
                    "staff_id": teacher['staff_id'],
                    "is_primary": True,
                    "start_date": "2024-08-15",
                    "end_date": "2025-06-15"
                })

                section_counter += 1

    mst_df = pd.DataFrame(mst_data)
    write_deltalake(os.path.join(DELTA_PATH, "master_schedule"), mst_df, mode="overwrite")

    sse_df = pd.DataFrame(section_staff_data)
    write_deltalake(os.path.join(DELTA_PATH, "section_staff"), sse_df, mode="overwrite")

    # ==========================================
    # 4. Generate Students (STU)
    # ==========================================
    print("  - Generating Students (STU)...")
    num_students = 500
    student_ids = range(10000, 10000 + num_students)

    students_data = []
    counselor_list = [s['staff_id'] for s in staff_data if s['job_class'] == 'Counselor']

    for sid in student_ids:
        grade = int(np.random.choice([9, 10, 11, 12], p=[0.28, 0.26, 0.24, 0.22]))
        students_data.append({
            "student_id": sid,
            "state_id": f"SSID{sid}",
            "last_name": f"StudentLN{sid}",
            "first_name": f"StudentFN{sid}",
            "middle_name": "M",
            "grade": grade,
            "gender": np.random.choice(["M", "F", "X"], p=[0.48, 0.48, 0.04]),
            "birthdate": (datetime.now() - timedelta(days=365*(int(grade)+5))).strftime("%Y-%m-%d"),
            "ethnicity": np.random.choice(["100", "200", "300", "400", "500", "600", "700"]),
            "school_id": 999,
            "counselor_id": np.random.choice(counselor_list) if counselor_list else "",
            "home_language": "ENG",
            "entry_date": "2024-08-15",
            "leave_date": "",
            "status": False, # Active
            "program": np.random.choice(["GenEd", "IEP", "504", "EL"], p=[0.7, 0.1, 0.1, 0.1])
        })

    students_df = pd.DataFrame(students_data)
    write_deltalake(os.path.join(DELTA_PATH, "students"), students_df, mode="overwrite")

    # ==========================================
    # 5. Generate Student Classes (SEC) & Grades (GRD)
    # ==========================================
    print("  - Generating Student Classes & Grades...")
    grades_data = []

    # Enroll students in 6 periods
    for student in students_data:
        sid = student['student_id']
        grade_level = student['grade']

        for period in periods:
            # Filter sections for this period
            period_sections = [s for s in mst_data if s['period'] == period]

            # Try to find a grade-appropriate course
            valid_sections = []
            for sec in period_sections:
                # Rough heuristic for grade matching
                if grade_level == 9 and ("9" in sec['course_title'] or "Algebra I" in sec['course_title'] or "Biology" in sec['course_title']):
                    valid_sections.append(sec)
                elif grade_level == 10 and ("10" in sec['course_title'] or "Geometry" in sec['course_title'] or "Chemistry" in sec['course_title']):
                    valid_sections.append(sec)
                elif grade_level == 11 and ("11" in sec['course_title'] or "Algebra II" in sec['course_title'] or "US History" in sec['course_title']):
                    valid_sections.append(sec)
                elif grade_level == 12 and ("12" in sec['course_title'] or "Gov" in sec['course_title']):
                    valid_sections.append(sec)
                elif "Art" in sec['course_title'] or "PE" in sec['course_title']: # Electives for anyone
                    valid_sections.append(sec)

            # Fallback if no specific match
            if not valid_sections:
                valid_sections = period_sections

            if not valid_sections:
                continue

            # Pick a section
            section = np.random.choice(valid_sections)

            # Generate Grade
            gpa_point = np.random.normal(2.8, 1.0)
            gpa_point = max(0.0, min(4.0, gpa_point))

            if gpa_point >= 3.7: mark = "A"; percent = np.random.randint(90, 100)
            elif gpa_point >= 2.7: mark = "B"; percent = np.random.randint(80, 89)
            elif gpa_point >= 1.7: mark = "C"; percent = np.random.randint(70, 79)
            elif gpa_point >= 0.7: mark = "D"; percent = np.random.randint(60, 69)
            else: mark = "F"; percent = np.random.randint(40, 59)

            grades_data.append({
                "student_id": sid,
                "school_id": 999,
                "section_id": section['section_id'],
                "course_id": section['course_id'],
                "term": "Fall",
                "mark": mark,
                "percent": percent,
                "credits_attempted": 5.0,
                "credits_earned": 5.0 if mark != "F" else 0.0,
                "citizenship": "O",
                "work_habits": "O",
                "comments": ""
            })

    grades_df = pd.DataFrame(grades_data)
    write_deltalake(os.path.join(DELTA_PATH, "grades"), grades_df, mode="overwrite")

    # ==========================================
    # 6. Generate Attendance (ATT)
    # ==========================================
    print("  - Generating Attendance (ATT)...")
    attendance_data = []

    # Generate for last 60 days
    start_date = datetime.now() - timedelta(days=60)
    dates = pd.date_range(start=start_date, end=datetime.now(), freq="B")

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")

        for student in students_data:
            # 95% attendance rate
            rand = np.random.random()

            if rand > 0.95: # Absent
                status = "A"
                code = np.random.choice(["I", "E", "U"]) # Illness, Excused, Unexcused
                minutes = 0

                attendance_data.append({
                    "student_id": student['student_id'],
                    "school_id": 999,
                    "date": date_str,
                    "status": status,
                    "code": code,
                    "minutes_absent": minutes
                })
            elif rand > 0.92: # Tardy
                status = "T"
                code = "T"
                minutes = np.random.randint(5, 30)

                attendance_data.append({
                    "student_id": student['student_id'],
                    "school_id": 999,
                    "date": date_str,
                    "status": status,
                    "code": code,
                    "minutes_absent": minutes
                })

    att_df = pd.DataFrame(attendance_data)
    write_deltalake(os.path.join(DELTA_PATH, "attendance"), att_df, mode="overwrite")

    print(f"Done! Aeries-compatible mock data generated in {DELTA_PATH}/")

if __name__ == "__main__":
    generate_mock_data()
