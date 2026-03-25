# Data Dictionary

Complete reference for all entities, attributes, and their definitions in the SIS Package.

**Last Updated**: January 26, 2026

---

## Quick Reference

| Entity | Attributes | Purpose | Example Records |
|--------|-----------|---------|-----------------|
| **students** | 27 | Student demographics and enrollment status | John Smith (STU00123) |
| **courses** | 18 | Course information and scheduling | Algebra I (MATH101) |
| **enrollment** | 23 | Student-course relationships and grades | John in Algebra I, Grade: 85 |
| **attendance** | 21 | Daily attendance tracking | John present 2026-01-20 |
| **academic_records** | 24 | Assignment grades and assessments | Algebra Test: 92/100 |

**Total**: 113 attributes across 5 core entities

---

## ENTITY: students

**Purpose**: Store student demographic, enrollment, and program information

**Relationships**:
- 1 student : many enrollments
- 1 student : many attendance records
- 1 student : many academic_records

### Attributes

#### Identity & Demographics (8 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| student_id | VARCHAR(20) | YES | Alphanumeric | STU00123 | Primary key, unique identifier |
| first_name | VARCHAR(100) | YES | Text | John | Student's first name |
| last_name | VARCHAR(100) | YES | Text | Smith | Student's last name |
| middle_name | VARCHAR(100) | NO | Text | Michael | Student's middle name |
| date_of_birth | DATE | YES | YYYY-MM-DD | 1995-05-10 | Format: 1995-05-10 |
| gender | VARCHAR(20) | NO | M/F/X/Other | M | Gender identity |
| ethnicity | VARCHAR(50) | NO | Text | Hispanic | Ethnicity category |
| cohort_year | INT | YES | YYYY | 2024 | Expected graduation year |

#### Enrollment Status (3 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| grade_level | INT | YES | 0-16 | 9 | Current grade level (0=K, 1-12=grades, 13-16=post-secondary) |
| enrollment_status | VARCHAR(30) | YES | Enum | Active | Active/Inactive/Graduated/Withdrawn/etc |
| school_id | VARCHAR(20) | YES | Code | SCH001 | School code/identifier |

#### Special Programs (6 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| special_education | VARCHAR(30) | NO | Y/N/Code | Y | Special education status |
| english_learner | VARCHAR(30) | NO | Y/N | N | English language learner status |
| economically_disadvantaged | VARCHAR(30) | NO | Y/N | Y | Economically disadvantaged flag |
| homeless_status | VARCHAR(30) | NO | Y/N | N | Homeless status |
| foster_care_status | VARCHAR(30) | NO | Y/N | N | Foster care status |
| military_family | VARCHAR(30) | NO | Y/N | N | Military connected family |

#### Contact Information (5 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| phone_number | VARCHAR(20) | NO | ###-###-#### | 555-123-4567 | Primary phone number |
| email_address | VARCHAR(100) | NO | Email | john@school.edu | School email address |
| address_line1 | VARCHAR(100) | NO | Text | 123 Main Street | Street address |
| address_city | VARCHAR(50) | NO | Text | Denver | City |
| address_state | VARCHAR(2) | NO | State Code | CO | State abbreviation |
| address_zip | VARCHAR(10) | NO | Numeric | 80203 | ZIP/postal code |

#### District Information (2 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| district_id | VARCHAR(20) | YES | Code | DIST001 | School district identifier |
| _sis_modified_date | TIMESTAMP | YES | YYYY-MM-DD HH:MM:SS | 2026-01-20 10:30:00 | Last modified in source SIS |

---

## ENTITY: courses

**Purpose**: Store course catalog, scheduling, and instructor information

**Relationships**:
- 1 course : many enrollments
- 1 course : 1 teacher (typically)
- 1 course : many attendance records

### Attributes

#### Identity & Catalog (5 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| course_id | VARCHAR(20) | YES | Alphanumeric | MATH101 | Primary key, unique identifier |
| course_code | VARCHAR(20) | YES | Code | ALG1 | Course code for transcript |
| course_name | VARCHAR(100) | YES | Text | Algebra I | Course title |
| course_description | VARCHAR(500) | NO | Text | Introduction to algebraic... | Course description |
| subject_area | VARCHAR(50) | YES | Code | Mathematics | Subject area (Math, English, etc) |

#### Scheduling & Level (5 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| grade_level | INT | YES | 0-16 | 9 | Grade level for course (0=K, 1-12=grades) |
| term | VARCHAR(20) | YES | Code | Spring | Semester/term (Spring, Fall, Year-round) |
| start_date | DATE | YES | YYYY-MM-DD | 2026-01-15 | Course start date |
| end_date | DATE | YES | YYYY-MM-DD | 2026-05-30 | Course end date |
| course_type | VARCHAR(30) | NO | Code | Honors | Course type (Regular, Honors, AP, IB, Dual, etc) |

#### Enrollment & Instructor (4 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| teacher_id | VARCHAR(20) | NO | Code | TCH001 | Primary instructor ID |
| max_enrollment | INT | NO | Numeric | 30 | Maximum students |
| min_enrollment | INT | NO | Numeric | 15 | Minimum to run course |
| status | VARCHAR(20) | YES | Code | Active | Active/Archived/Cancelled |

#### Value & Metadata (3 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| credit_value | DECIMAL(3,2) | YES | 0.0-4.0 | 1.0 | Credits awarded (0.5=half credit) |
| school_id | VARCHAR(20) | YES | Code | SCH001 | School where course offered |
| _sis_modified_date | TIMESTAMP | YES | YYYY-MM-DD HH:MM:SS | 2026-01-20 10:30:00 | Last modified in source SIS |

---

## ENTITY: enrollment

**Purpose**: Store student-course relationships, grades, and attendance metrics

**Relationships**:
- many enrollments : 1 student
- many enrollments : 1 course
- 1 enrollment : many attendance records

### Attributes

#### Identity & Timing (7 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| enrollment_id | VARCHAR(20) | YES | Alphanumeric | ENR00001 | Primary key, unique identifier |
| student_id | VARCHAR(20) | YES | Code | STU00123 | Foreign key to students |
| course_id | VARCHAR(20) | YES | Code | MATH101 | Foreign key to courses |
| school_id | VARCHAR(20) | YES | Code | SCH001 | School where enrolled |
| term | VARCHAR(20) | YES | Code | Spring | Term/semester |
| enrollment_date | DATE | YES | YYYY-MM-DD | 2026-01-15 | Date student enrolled |
| completion_date | DATE | NO | YYYY-MM-DD | 2026-05-30 | Date course completed/dropped |

#### Academic Performance (6 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| final_grade_letter | VARCHAR(2) | NO | A-F | A | Letter grade (A, B, C, D, F, I=incomplete) |
| final_grade_numeric | DECIMAL(5,2) | NO | 0-100 | 85.5 | Numeric grade (0-100 scale) |
| credits_earned | DECIMAL(3,2) | NO | 0.0-4.0 | 1.0 | Credits earned for course |
| credits_attempted | DECIMAL(3,2) | YES | 0.0-4.0 | 1.0 | Credits attempted |
| enrollment_status | VARCHAR(30) | YES | Enum | Completed | Completed/Dropped/Withdrawn/In Progress |
| grade_scale | VARCHAR(10) | NO | Code | 4.0 | Grading scale (4.0, 100-point, etc) |

#### Attendance (7 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| attendance_days | INT | YES | 0-365 | 165 | Days present in course |
| absence_count | INT | YES | 0+ | 5 | Unexcused absences |
| absence_count_excused | INT | NO | 0+ | 3 | Excused absences |
| tardy_count | INT | YES | 0+ | 2 | Number of times late |
| attendance_rate | DECIMAL(3,3) | YES | 0.000-1.000 | 0.970 | Attendance rate (0-1 scale) |
| absence_pattern | VARCHAR(50) | NO | Code | intermittent | Pattern type (none, regular, intermittent, chronic) |
| days_in_course | INT | YES | 1-365 | 170 | Total instructional days in term |

#### Metadata (2 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| is_current | BOOLEAN | YES | true/false | true | Current term or historical |
| _sis_modified_date | TIMESTAMP | YES | YYYY-MM-DD HH:MM:SS | 2026-01-20 10:30:00 | Last modified in source SIS |

---

## ENTITY: attendance

**Purpose**: Store daily attendance records for tracking patterns and trends

**Relationships**:
- many records : 1 student
- many records : 1 course
- many records : 1 enrollment (implicitly)

### Attributes

#### Identity & Scheduling (7 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| attendance_id | VARCHAR(20) | YES | Alphanumeric | ATT00001 | Primary key, unique identifier |
| student_id | VARCHAR(20) | YES | Code | STU00123 | Foreign key to students |
| course_id | VARCHAR(20) | YES | Code | MATH101 | Foreign key to courses |
| school_id | VARCHAR(20) | YES | Code | SCH001 | School |
| attendance_date | DATE | YES | YYYY-MM-DD | 2026-01-20 | Date of attendance record |
| term | VARCHAR(20) | YES | Code | Spring | Term/semester |
| enrollment_id | VARCHAR(20) | NO | Code | ENR00001 | Foreign key to enrollment (optional) |

#### Daily Status (5 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| status | VARCHAR(20) | YES | Code | Present | Present/Absent/Tardy/Excused/Suspended |
| is_present | BOOLEAN | YES | true/false | true | Day considered present |
| is_absent | BOOLEAN | YES | true/false | false | Day considered absent |
| is_tardy | BOOLEAN | YES | true/false | false | Day student was tardy |
| is_excused | BOOLEAN | YES | true/false | false | Absence was excused |

#### Cumulative Metrics (6 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| cumulative_present | INT | YES | 0+ | 165 | Running total of present days |
| cumulative_absent | INT | YES | 0+ | 5 | Running total of absent days |
| cumulative_tardy | INT | YES | 0+ | 2 | Running total of tardy instances |
| cumulative_days_in_term | INT | YES | 1+ | 170 | Running total of instructional days |
| attendance_rate_ytd | DECIMAL(3,3) | YES | 0.000-1.000 | 0.970 | Year-to-date attendance rate |
| absent_pattern_ytd | VARCHAR(50) | NO | Code | intermittent | YTD absence pattern |

#### Metadata (3 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| reason_code | VARCHAR(20) | NO | Code | SICK | Reason for absence (SICK, FAMILY, UNEXCUSED, etc) |
| note | VARCHAR(200) | NO | Text | Doctor's note on file | Additional notes |
| _sis_modified_date | TIMESTAMP | YES | YYYY-MM-DD HH:MM:SS | 2026-01-20 10:30:00 | Last modified in source SIS |

---

## ENTITY: academic_records

**Purpose**: Store assignment grades, test scores, and proficiency levels

**Relationships**:
- many records : 1 student
- many records : 1 course
- many records : 1 enrollment (implicitly)

### Attributes

#### Identity & Classification (6 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| record_id | VARCHAR(20) | YES | Alphanumeric | ARK00001 | Primary key, unique identifier |
| student_id | VARCHAR(20) | YES | Code | STU00123 | Foreign key to students |
| course_id | VARCHAR(20) | YES | Code | MATH101 | Foreign key to courses |
| school_id | VARCHAR(20) | YES | Code | SCH001 | School |
| record_type | VARCHAR(20) | YES | Code | Assignment | Type: Assignment/Test/Quiz/Exam/Project |
| term | VARCHAR(20) | YES | Code | Spring | Term/semester |

#### Assignment Information (6 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| assignment_name | VARCHAR(100) | YES | Text | Chapter 3 Quiz | Assignment/test name |
| assignment_date | DATE | YES | YYYY-MM-DD | 2026-01-20 | Date assignment given |
| due_date | DATE | NO | YYYY-MM-DD | 2026-01-27 | Date assignment due |
| submission_date | DATE | NO | YYYY-MM-DD | 2026-01-25 | Date student submitted |
| is_late | BOOLEAN | NO | true/false | false | Submitted after due date |
| points_possible | DECIMAL(7,2) | YES | 0.00+ | 100.00 | Maximum possible points |

#### Scoring (5 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| points_earned | DECIMAL(7,2) | YES | 0.00+ | 85.50 | Points earned by student |
| percent_earned | DECIMAL(5,2) | YES | 0.00-100.00 | 85.50 | Percentage (0-100) |
| letter_grade | VARCHAR(2) | NO | A-F | B | Letter grade (A, B, C, D, F, I) |
| numeric_grade | INT | NO | 0-100 | 85 | Rounded numeric grade |
| raw_score | INT | NO | 0+ | 86 | Raw unscaled score |

#### Standards & Proficiency (4 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| standard_code | VARCHAR(20) | NO | Code | 8.EE.7 | Standard addressed (e.g., Common Core) |
| standard_name | VARCHAR(200) | NO | Text | Solve linear equations | Standard description |
| proficiency_level | VARCHAR(20) | NO | Code | Proficient | Not Yet/Developing/Proficient/Advanced |
| mastery_level | VARCHAR(20) | NO | Code | Proficient | Similar to proficiency_level |

#### Metadata & Analysis (3 attributes)

| Attribute | Type | Required | Format | Example | Notes |
|-----------|------|----------|--------|---------|-------|
| is_formative | BOOLEAN | YES | true/false | false | Formative vs summative assessment |
| feedback | VARCHAR(500) | NO | Text | Excellent work! | Teacher feedback |
| _sis_modified_date | TIMESTAMP | YES | YYYY-MM-DD HH:MM:SS | 2026-01-20 10:30:00 | Last modified in source SIS |

---

## Data Validation Rules

### By Entity

#### Students
- **Null Checks**: student_id, first_name, last_name required
- **Unique Constraints**: student_id must be unique
- **Range Checks**: grade_level [0, 16], cohort_year [1900, 2050]
- **Pattern Checks**: email_address (valid email format)

#### Courses
- **Null Checks**: course_id, course_code, course_name required
- **Unique Constraints**: course_id must be unique
- **Range Checks**: credit_value [0.0, 4.0], grade_level [0, 16]
- **Logic Checks**: end_date > start_date

#### Enrollment
- **Null Checks**: enrollment_id, student_id, course_id required
- **Range Checks**: final_grade_numeric [0, 100], credits_earned [0, 4]
- **Logic Checks**: completion_date >= enrollment_date, credits_earned <= credits_attempted
- **Referential Integrity**: student_id exists in students, course_id exists in courses

#### Attendance
- **Null Checks**: attendance_id, student_id, course_id, status required
- **Range Checks**: attendance_rate [0.0, 1.0], cumulative_present >= 0
- **Logic Checks**: attendance_rate = cumulative_present / cumulative_days_in_term

#### Academic_Records
- **Null Checks**: record_id, student_id, course_id required
- **Range Checks**: points_earned [0, points_possible], percent_earned [0, 100]
- **Logic Checks**: percent_earned = (points_earned / points_possible) * 100

---

## Data Quality Metrics

### By Entity

| Entity | Min Records | Max Null % | Max Dup % | Quality Gate |
|--------|------------|-----------|-----------|--------------|
| students | 100 | 5% | 1% | PASS if all criteria met |
| courses | 10 | 10% | 0% | PASS if all criteria met |
| enrollment | 50 | 5% | 1% | PASS if all criteria met |
| attendance | 100 | 10% | 1% | PASS if all criteria met |
| academic_records | 50 | 15% | 1% | PASS if all criteria met |

### Overall

- **Max Null %**: 5% of all cells can be null
- **Max Duplicate %**: 1% of records can be duplicates
- **Max Validation Error %**: 2% of records can fail validation
- **Min Record Count**: At least 100 records in largest entity

---

## Privacy Classification

### Data Classifications

**PUBLIC** (no restriction):
- Course codes, names
- Grade levels (9, 10, 11, etc.)
- Enrollment status codes

**INTERNAL** (school staff only):
- Grades, assessment scores
- Attendance records
- Academic performance

**CONFIDENTIAL** (authorized staff only):
- Student names
- Contact information
- Special program flags
- Teacher assignments

**RESTRICTED** (admins only):
- Date of birth
- Special education status
- Homeless/foster care status

---

## Transformations by Stage

### Stage 1 → Stage 2A

**Field Mapping**: SIS column names → standard schema
- StudentNumber → student_id
- FirstName → first_name
- etc.

**Type Conversion**: String values → proper data types
- "05/10/1995" → DATE 1995-05-10
- "9" → INT 9

**Validation**: Apply rules to ensure data quality

**Deduplication**: Remove exact duplicates, keep latest by timestamp

### Stage 2A → Stage 2B

**Hashing**: student_id → hashed_student_id
- Deterministic (same input = same output)
- One-way (cannot reverse)

**Masking**: first_name → Jo****
- Irreversible
- Preserves data availability (formatted)

**Aggregation**: Create summary statistics
- Attendance rate by student
- Grade average by student

### Stage 2B → Stage 3

**Joining**: Combine related entities
- students ✕ enrollment ✕ courses
- enrollment ✕ attendance

**Feature Engineering**: Create computed fields
- engagement_score = (attendance * 0.3) + (grades * 0.7)
- at_risk_flag = grade < 60 OR attendance < 0.80

**Aggregation**: Create summary tables
- Per-student metrics
- Per-course metrics

---

## Reference & Support

For more information:

- **Configuration**: See `../config/README.md`
- **Schemas**: See `../SCHEMAS.md`
- **Architecture**: See `ARCHITECTURE.md`
- **Privacy**: See `PRIVACY_RULES.md`
- **Troubleshooting**: See `TROUBLESHOOTING.md`

---

**Last Updated**: January 26, 2026  
**Version**: 1.0  
**Entities**: 5  
**Attributes**: 113
