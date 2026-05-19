# SIS Package Data Schemas

Complete schema documentation for all entities in the SIS data package.

---

## Schema Overview

The SIS package includes 5 core entities covering K-12 student data:

| Entity | Records | Attributes | Privacy Rules | Purpose |
|--------|---------|-----------|----------------|---------|
| **students** | 5K-50K | 27 | Hash IDs, Mask PII | Student demographics & status |
| **courses** | 100-500 | 18 | Hash teacher IDs | Course catalog & scheduling |
| **enrollment** | 50K-500K | 23 | Hash student IDs | Student-course relationships |
| **attendance** | 1M+ | 21 | Hash IDs | Daily attendance tracking |
| **academic_records** | 5M+ | 24 | Hash IDs | Assignment grades & performance |

---

## Students Entity

**Purpose**: Core student demographic and enrollment status information  
**Stage 1 Table**: `stage1.students`  
**Stage 2A Table**: `stage2a.students`  
**Stage 2B Table**: `stage2b.students` (pseudonymized)

### Attributes (27)

| # | Attribute | Type | Pseudonymization | Description | Example |
|---|-----------|------|------------------|-------------|---------|
| 1 | student_id | VARCHAR(20) | **hash** | Unique student identifier from SIS | STU001 → abc123... |
| 2 | first_name | VARCHAR(100) | **mask** | Student first name | Alice → A*** |
| 3 | last_name | VARCHAR(100) | **mask** | Student last name | Smith → S*** |
| 4 | middle_name | VARCHAR(100) | **mask** | Student middle name | Robert → R*** |
| 5 | date_of_birth | DATE | **hash** | Student birthdate (FERPA) | 2008-05-15 → hash... |
| 6 | gender | VARCHAR(10) | **no-op** | Gender (M/F/X/Other) | F |
| 7 | ethnicity | VARCHAR(50) | **no-op** | Ethnicity (for demographics) | Hispanic |
| 8 | grade_level | INT | **no-op** | Current grade (0-16, K=0) | 9 |
| 9 | school_id | VARCHAR(20) | **no-op** | School code | SCH001 |
| 10 | district_id | VARCHAR(20) | **no-op** | District code | DIST001 |
| 11 | cohort_year | INT | **no-op** | Expected graduation year | 2026 |
| 12 | enrollment_status | VARCHAR(30) | **no-op** | Status (active/inactive/transferred) | active |
| 13 | special_education | BOOLEAN | **no-op** | Enrolled in SPED services | TRUE |
| 14 | english_learner | BOOLEAN | **no-op** | English learner flag | TRUE |
| 15 | economically_disadvantaged | BOOLEAN | **no-op** | Low SES indicator | TRUE |
| 16 | homeless_status | BOOLEAN | **no-op** | Homeless student flag | FALSE |
| 17 | foster_care_status | BOOLEAN | **no-op** | Foster care indicator | FALSE |
| 18 | military_family | BOOLEAN | **no-op** | Military-connected flag | FALSE |
| 19 | phone_number | VARCHAR(20) | **mask** | Contact phone (FERPA) | 555-1234 → ***-**** |
| 20 | email_address | VARCHAR(100) | **mask** | Contact email (FERPA) | alice@school.edu → a***@... |
| 21 | address_line1 | VARCHAR(100) | **mask** | Street address (FERPA) | 123 Main St → *** |
| 22 | address_city | VARCHAR(50) | **mask** | City (FERPA) | NYC → *** |
| 23 | address_state | VARCHAR(2) | **mask** | State/Province (FERPA) | NY → ** |
| 24 | address_zip | VARCHAR(10) | **mask** | ZIP/Postal code (FERPA) | 10001 → *** |
| 25 | _loaded_date | TIMESTAMP | **no-op** | Date loaded to Stage 1 | 2026-01-26 14:30:00 |
| 26 | _updated_date | TIMESTAMP | **no-op** | Last update timestamp | 2026-01-26 14:30:00 |
| 27 | _sis_modified_date | TIMESTAMP | **no-op** | Last modification in SIS | 2026-01-25 16:45:00 |

### Sample Record (Stage 2B - Anonymized)

```json
{
  "student_id": "abc123def456ghi789",          // Hashed
  "first_name": "A***",                        // Masked
  "last_name": "S***",                         // Masked
  "middle_name": "R***",                       // Masked
  "date_of_birth": "789xyz...",                // Hashed
  "gender": "F",                               // No-op
  "ethnicity": "Hispanic",                     // No-op
  "grade_level": 9,                            // No-op
  "school_id": "SCH001",                       // No-op
  "enrollment_status": "active",               // No-op
  "special_education": true,                   // No-op
  "english_learner": true,                     // No-op
  "economically_disadvantaged": true           // No-op
}
```

---

## Courses Entity

**Purpose**: Course catalog, scheduling, and instructor information  
**Stage 1 Table**: `stage1.courses`  
**Stage 2A Table**: `stage2a.courses`  
**Stage 2B Table**: `stage2b.courses` (pseudonymized)

### Attributes (18)

| # | Attribute | Type | Pseudonymization | Description | Example |
|---|-----------|------|------------------|-------------|---------|
| 1 | course_id | VARCHAR(20) | **no-op** | Unique course ID | CRS001 |
| 2 | school_id | VARCHAR(20) | **no-op** | School offering course | SCH001 |
| 3 | course_code | VARCHAR(20) | **no-op** | Course code (e.g., ELA101) | ELA101 |
| 4 | course_name | VARCHAR(100) | **no-op** | Human-readable name | English Language Arts I |
| 5 | course_description | VARCHAR(500) | **no-op** | Full description | Introduction to literary analysis... |
| 6 | subject_area | VARCHAR(50) | **no-op** | Subject (Math/ELA/Science/etc) | ELA |
| 7 | grade_level | VARCHAR(20) | **no-op** | Target grade(s) | 9-10 |
| 8 | credit_value | FLOAT | **no-op** | Credit hours | 1.0 |
| 9 | course_type | VARCHAR(30) | **no-op** | Type (regular/honors/AP/IB) | regular |
| 10 | teacher_id | VARCHAR(20) | **hash** | Primary instructor | TCH001 → abc... |
| 11 | max_enrollment | INT | **no-op** | Maximum students | 30 |
| 12 | min_enrollment | INT | **no-op** | Minimum students | 15 |
| 13 | term | VARCHAR(20) | **no-op** | Term (semester/trimester/year) | Fall2026 |
| 14 | start_date | DATE | **no-op** | Course start date | 2026-09-01 |
| 15 | end_date | DATE | **no-op** | Course end date | 2026-12-15 |
| 16 | status | VARCHAR(20) | **no-op** | Status (active/inactive/cancelled) | active |
| 17 | _loaded_date | TIMESTAMP | **no-op** | Date loaded | 2026-01-26 14:30:00 |
| 18 | _updated_date | TIMESTAMP | **no-op** | Last update | 2026-01-26 14:30:00 |

---

## Enrollment Entity

**Purpose**: Student-course relationships, grades, and completion tracking  
**Stage 1 Table**: `stage1.enrollment`  
**Stage 2A Table**: `stage2a.enrollment`  
**Stage 2B Table**: `stage2b.enrollment` (pseudonymized)

### Attributes (23)

| # | Attribute | Type | Pseudonymization | Description | Example |
|---|-----------|------|------------------|-------------|---------|
| 1 | enrollment_id | VARCHAR(30) | **no-op** | Unique enrollment ID | ENR001 |
| 2 | student_id | VARCHAR(20) | **hash** | Student ID (links to students) | STU001 → abc... |
| 3 | course_id | VARCHAR(20) | **no-op** | Course ID (links to courses) | CRS001 |
| 4 | school_id | VARCHAR(20) | **no-op** | School | SCH001 |
| 5 | term | VARCHAR(20) | **no-op** | Academic term | Fall2026 |
| 6 | enrollment_date | DATE | **no-op** | Date enrolled | 2026-08-20 |
| 7 | completion_date | DATE | **no-op** | Date completed (NULL if ongoing) | 2026-12-15 |
| 8 | enrollment_status | VARCHAR(30) | **no-op** | Status (active/completed/dropped) | completed |
| 9 | final_grade_letter | VARCHAR(2) | **no-op** | Letter grade (A-F) | A |
| 10 | final_grade_numeric | FLOAT | **no-op** | Numeric grade (0-100) | 92.5 |
| 11 | credits_earned | FLOAT | **no-op** | Credits earned | 1.0 |
| 12 | credits_attempted | FLOAT | **no-op** | Credits attempted | 1.0 |
| 13 | weighted_gpa_impact | FLOAT | **no-op** | GPA weight factor | 1.0 |
| 14 | attendance_days | INT | **no-op** | Days attended | 175 |
| 15 | absence_count | INT | **no-op** | Total absences | 5 |
| 16 | tardy_count | INT | **no-op** | Times tardy | 2 |
| 17 | excused_absence_count | INT | **no-op** | Excused absences | 3 |
| 18 | unexcused_absence_count | INT | **no-op** | Unexcused absences | 2 |
| 19 | engagement_flag | BOOLEAN | **no-op** | Low engagement indicator | FALSE |
| 20 | academic_risk_flag | BOOLEAN | **no-op** | Academic risk indicator | FALSE |
| 21 | _loaded_date | TIMESTAMP | **no-op** | Date loaded | 2026-01-26 14:30:00 |
| 22 | _updated_date | TIMESTAMP | **no-op** | Last update | 2026-01-26 14:30:00 |
| 23 | _sis_modified_date | TIMESTAMP | **no-op** | Last SIS modification | 2026-01-25 16:45:00 |

---

## Attendance Entity

**Purpose**: Daily attendance tracking and absence patterns  
**Stage 1 Table**: `stage1.attendance`  
**Stage 2A Table**: `stage2a.attendance`  
**Stage 2B Table**: `stage2b.attendance` (pseudonymized)

### Attributes (21)

| # | Attribute | Type | Pseudonymization | Description | Example |
|---|-----------|------|------------------|-------------|---------|
| 1 | attendance_id | VARCHAR(30) | **no-op** | Unique attendance ID | ATT001 |
| 2 | student_id | VARCHAR(20) | **hash** | Student ID | STU001 → abc... |
| 3 | school_id | VARCHAR(20) | **no-op** | School | SCH001 |
| 4 | attendance_date | DATE | **no-op** | Date of attendance | 2026-09-15 |
| 5 | is_present | BOOLEAN | **no-op** | Present (TRUE/FALSE) | TRUE |
| 6 | absence_type | VARCHAR(30) | **no-op** | Type (excused/unexcused/medical/OSS) | excused |
| 7 | absence_reason | VARCHAR(100) | **no-op** | Reason (illness/appointment/etc) | dental appointment |
| 8 | period_or_class | VARCHAR(10) | **no-op** | Period/class identifier | 1st |
| 9 | course_id | VARCHAR(20) | **no-op** | Course ID (if period-specific) | CRS001 |
| 10 | teacher_id | VARCHAR(20) | **hash** | Teacher ID | TCH001 → xyz... |
| 11 | checkin_time | TIME | **no-op** | Check-in time | 08:30:00 |
| 12 | checkout_time | TIME | **no-op** | Check-out time | 15:45:00 |
| 13 | partial_absence_duration | INT | **no-op** | Duration in minutes | 30 |
| 14 | tardy_flag | BOOLEAN | **no-op** | Late arrival | FALSE |
| 15 | early_departure_flag | BOOLEAN | **no-op** | Early departure | FALSE |
| 16 | chronic_absence_flag | BOOLEAN | **no-op** | Chronic absentee (<90%) | FALSE |
| 17 | attendance_pattern | VARCHAR(30) | **no-op** | Pattern (improving/declining/stable) | stable |
| 18 | makeup_assignment_required | BOOLEAN | **no-op** | Makeup work needed | FALSE |
| 19 | parent_notification_sent | BOOLEAN | **no-op** | Parent notified | TRUE |
| 20 | _loaded_date | TIMESTAMP | **no-op** | Date loaded | 2026-01-26 14:30:00 |
| 21 | _updated_date | TIMESTAMP | **no-op** | Last update | 2026-01-26 14:30:00 |

---

## Academic Records Entity

**Purpose**: Assignment-level grades and performance data  
**Stage 1 Table**: `stage1.academic_records`  
**Stage 2A Table**: `stage2a.academic_records`  
**Stage 2B Table**: `stage2b.academic_records` (pseudonymized)

### Attributes (24)

| # | Attribute | Type | Pseudonymization | Description | Example |
|---|-----------|------|------------------|-------------|---------|
| 1 | record_id | VARCHAR(30) | **no-op** | Unique record ID | ACD001 |
| 2 | student_id | VARCHAR(20) | **hash** | Student ID | STU001 → abc... |
| 3 | course_id | VARCHAR(20) | **no-op** | Course ID | CRS001 |
| 4 | school_id | VARCHAR(20) | **no-op** | School | SCH001 |
| 5 | term | VARCHAR(20) | **no-op** | Academic term | Fall2026 |
| 6 | assignment_id | VARCHAR(30) | **no-op** | Unique assignment | ASG001 |
| 7 | assignment_name | VARCHAR(100) | **no-op** | Assignment name | Essay 1: Character Analysis |
| 8 | assignment_type | VARCHAR(30) | **no-op** | Type (homework/quiz/exam/project) | homework |
| 9 | assignment_due_date | DATE | **no-op** | Due date | 2026-09-20 |
| 10 | assignment_submission_date | DATE | **no-op** | Submission date (NULL if not submitted) | 2026-09-19 |
| 11 | points_earned | FLOAT | **no-op** | Points earned | 45.0 |
| 12 | points_possible | FLOAT | **no-op** | Total points | 50.0 |
| 13 | assignment_grade_percent | FLOAT | **no-op** | Percentage (0-100) | 90.0 |
| 14 | assignment_grade_letter | VARCHAR(2) | **no-op** | Letter grade | A |
| 15 | submission_status | VARCHAR(20) | **no-op** | Status (submitted/missing/excused) | submitted |
| 16 | on_time_flag | BOOLEAN | **no-op** | Submitted on time | TRUE |
| 17 | late_days | INT | **no-op** | Days late (0 if on time) | 0 |
| 18 | teacher_id | VARCHAR(20) | **hash** | Teacher ID | TCH001 → xyz... |
| 19 | feedback_provided | BOOLEAN | **no-op** | Feedback given | TRUE |
| 20 | feedback_date | DATE | **no-op** | Feedback date | 2026-09-21 |
| 21 | rubric_score | FLOAT | **no-op** | Rubric score | 4.5 |
| 22 | mastery_level | VARCHAR(20) | **no-op** | Level (novice/developing/proficient/advanced) | proficient |
| 23 | _loaded_date | TIMESTAMP | **no-op** | Date loaded | 2026-01-26 14:30:00 |
| 24 | _updated_date | TIMESTAMP | **no-op** | Last update | 2026-01-26 14:30:00 |

---

## Data Quality Standards

### Null Value Handling

**Required (No Nulls)**:
- student_id, course_id, enrollment_id
- first_name, last_name (if student record)
- grade_level, school_id

**Allowed (May Be Null)**:
- middle_name, phone_number, email_address
- completion_date (for ongoing enrollments)
- feedback_date (if no feedback provided)

### Value Ranges

| Field | Min | Max | Unit |
|-------|-----|-----|------|
| grade_level | 0 | 16 | Grade (0=K) |
| final_grade_numeric | 0 | 100 | Percentage |
| credits_earned | 0 | 4 | Credits |
| GPA | 0.0 | 4.0 | Scale |

### Data Validation Rules

```yaml
students:
  null_check: [student_id, first_name, last_name]
  unique_check: [student_id]
  range_check:
    grade_level: [0, 16]

enrollment:
  null_check: [enrollment_id, student_id, course_id]
  range_check:
    final_grade_numeric: [0, 100]
    credits_earned: [0, 4]
  logic_check:
    - completion_date >= enrollment_date (if completion_date not null)
    - credits_earned <= credits_attempted

academic_records:
  null_check: [record_id, student_id, assignment_id]
  range_check:
    points_earned: [0, points_possible]
    assignment_grade_percent: [0, 100]
  logic_check:
    - points_earned <= points_possible
    - (points_earned/points_possible)*100 == assignment_grade_percent
```

---

## Related Documentation

- **Setup Guide**: `SETUP_GUIDE.md` - Configuration and installation
- **Architecture**: `docs/ARCHITECTURE.md` - Data flow and pipelines
- **Privacy Rules**: `docs/PRIVACY_RULES.md` - Detailed pseudonymization
- **Data Dictionary**: `docs/DATA_DICTIONARY.md` - Auto-generated reference

---

**Last Updated**: January 26, 2026
