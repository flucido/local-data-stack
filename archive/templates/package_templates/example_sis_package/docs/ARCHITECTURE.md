# Package Architecture

Complete technical documentation of the SIS package architecture, data flows, and system design.

---

## Overview

The SIS Package Template implements a privacy-first data integration architecture following Open Education Analytics (OEA) reference patterns. Data flows through 4 stages with increasing refinement and pseudonymization.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SIS Source System                          │
│  (PowerSchool, Skyward, Infinite Campus, Generic SQL Server)   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ SQL Query / API Extract
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  EXTRACTION LAYER                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • Validate connection & credentials                     │  │
│  │ • Execute extraction query with date filtering          │  │
│  │ • Handle batch modes: delta/additive/snapshot           │  │
│  │ • Export to CSV/JSON with configured options            │  │
│  │ • Log extraction metrics (record count, duration, size)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Output: sis_exports/{students,courses,enrollment,attendance}.csv
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  │ CSV/JSON Files
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: RAW DATA (Landing Zone)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • Organize by date partition: YYYY/MM/DD                │  │
│  │ • Preserve original column names & data types           │  │
│  │ • Add metadata (_load_timestamp, _record_id)            │  │
│  │ • Audit trail: all extractions preserved                │  │
│  │ • Error recovery: restore point if issues found         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Storage: stage1/{2026/01/20/students.csv, ...}
│  Purpose: Audit trail, compliance, recovery
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  │ Transformation Pipeline
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2A: NORMALIZED DATA (Cleaning & Validation)             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ FIELD MAPPING:                                           │  │
│  │ • StudentNumber → student_id                            │  │
│  │ • FirstName → first_name                                │  │
│  │ • Parse dates: "01/20/2026" → 2026-01-20               │  │
│  │ • Convert types: VARCHAR → INT, FLOAT, BOOLEAN          │  │
│  │                                                          │  │
│  │ DATA VALIDATION:                                         │  │
│  │ • Null checks: required fields cannot be NULL           │  │
│  │ • Unique checks: ID fields must be unique               │  │
│  │ • Range checks: grades [0,100], ages [0,120]           │  │
│  │ • Pattern checks: email, phone format validation        │  │
│  │ • SQL checks: custom validation logic                   │  │
│  │                                                          │  │
│  │ DEDUPLICATION:                                           │  │
│  │ • Remove exact duplicates                               │  │
│  │ • Keep latest by timestamp (_sis_modified_date)         │  │
│  │ • Flag suspicious duplicates for review                 │  │
│  │                                                          │  │
│  │ QUALITY GATES:                                           │  │
│  │ • Max 5% null values allowed                            │  │
│  │ • Max 1% duplicates allowed                             │  │
│  │ • Min 100 records required                              │  │
│  │ • Fail if >2% validation errors                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Storage: stage2a/{students, courses, enrollment, ...}
│  Purpose: Analysis-ready normalized data
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  │ Pseudonymization Pipeline
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2B: REFINED DATA (Privacy & Aggregation)                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PSEUDONYMIZATION RULES:                                 │  │
│  │                                                          │  │
│  │ HASH (Deterministic):                                   │  │
│  │ • student_id: STU00123 → a7f3e8d2c1b45e9f2a3b           │  │
│  │ • Consistent hash for same input (linkable)             │  │
│  │ • Used for: student_id, teacher_id, date_of_birth      │  │
│  │ • Authorized users can link across datasets             │  │
│  │                                                          │  │
│  │ MASK (Irreversible):                                    │  │
│  │ • first_name: John → Jo****                             │  │
│  │ • email: user@example.com → us****@ex****.***           │  │
│  │ • address: 123 Main St → *** M**** **                   │  │
│  │ • Cannot reverse to original value                      │  │
│  │ • Used for: names, addresses, contact info              │  │
│  │                                                          │  │
│  │ NO-OP (Unchanged):                                       │  │
│  │ • grade_level: 9 → 9 (no change)                        │  │
│  │ • enrollment_status: Active → Active                    │  │
│  │ • attendance_rate: 0.95 → 0.95                          │  │
│  │ • Used for: non-sensitive fields                        │  │
│  │                                                          │  │
│  │ AGGREGATION:                                             │  │
│  │ • Group enrollment by hashed_student_id + course        │  │
│  │ • Calculate: attendance_rate, grade_average             │  │
│  │ • Create engagement metrics                             │  │
│  │ • Suppress small groups (<5 students)                   │  │
│  │                                                          │  │
│  │ VIEW CREATION:                                           │  │
│  │ • Teacher views: see their own course data               │  │
│  │ • Admin views: district-wide aggregated data             │  │
│  │ • Researcher views: anonymized data for studies         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Storage: stage2b/{students, courses, enrollment, ...}
│  Purpose: Privacy-compliant analysis data
│  Access: Authorized users only (RBAC)
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  │ Analytics Pipeline
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: ANALYTICS DATA (Ready for Dashboards)               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ENTITY JOINING:                                          │  │
│  │ • Join students + enrollment + courses                  │  │
│  │ • Join with attendance + academic_records               │  │
│  │ • Denormalized for fast dashboard queries               │  │
│  │                                                          │  │
│  │ FEATURE ENGINEERING:                                    │  │
│  │ • attendance_rate: present_days / total_days            │  │
│  │ • grade_average: AVG(all_assignment_grades)             │  │
│  │ • engagement_score: (attendance*0.3 + grades*0.7)      │  │
│  │ • trend_flag: improving/declining/stable                │  │
│  │ • at_risk_flag: grade<60 OR attendance<0.80             │  │
│  │                                                          │  │
│  │ TABLE CREATION:                                          │  │
│  │ • student_performance: all metrics per student/course   │  │
│  │ • course_summary: aggregate course metrics               │  │
│  │ • teacher_view: course and student data                 │  │
│  │ • district_summary: district-wide KPIs                  │  │
│  │                                                          │  │
│  │ FINAL VALIDATION:                                        │  │
│  │ • Quality checks on computed features                   │  │
│  │ • Null value checks                                     │  │
│  │ • Range validation for metrics (0-1 for rates)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Storage: stage3/{student_performance, course_summary, ...}
│  Purpose: Clean, analytics-ready data for dashboards
│  Access: All authorized education staff
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  │ Dashboard Query
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│  VISUALIZATION LAYER                                            │
│  • Grafana: Real-time dashboards with drill-down               │
│  • Superset: Self-service analytics with SQL editor            │
│  • Metabase: Question & answer interface                       │
│  • Power BI: Executive dashboards                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Stages

### Stage 1: Raw (Landing Zone)

**Purpose**: Preserve raw data as extracted from SIS for audit and recovery

**Characteristics**:
- Original column names unchanged
- Original data types preserved
- Date partitioned (YYYY/MM/DD)
- Minimal processing
- Complete audit trail

**Schema Example**:
```
Stage 1 Student Record:
{
  StudentNumber: "STU00123",
  FirstName: "John",
  LastName: "Smith",
  BirthDate: "05/10/1995",
  GradeLevel: "9",
  Status: "Active",
  LASTUPDATEDATE: "2026-01-20 10:30:00"
}
```

**Storage**:
- Format: CSV/JSON
- Location: `stage1/2026/01/20/students.csv`
- Size: Original + metadata

---

### Stage 2A: Normalized (Cleaned)

**Purpose**: Standardize data structure, validate quality, ensure consistency

**Transformations Applied**:

1. **Field Mapping**
   - Rename to standard schema
   - `StudentNumber` → `student_id`
   - Consistent naming across all SIS vendors

2. **Type Conversion**
   - Date parsing: "05/10/1995" → DATE 1995-05-10
   - Numeric: "9" → INT 9
   - Boolean: "Y" → BOOLEAN true

3. **Validation**
   - Enforce NOT NULL on required fields
   - Check unique constraints (IDs)
   - Range validation (grade 0-16)
   - Pattern matching (email format)

4. **Deduplication**
   - Remove exact duplicates
   - Keep latest by `_sis_modified_date`

**Schema Example**:
```
Stage 2A Student Record:
{
  student_id: "STU00123",
  first_name: "John",
  last_name: "Smith",
  date_of_birth: 1995-05-10,
  grade_level: 9,
  enrollment_status: "Active",
  _sis_modified_date: 2026-01-20 10:30:00
}
```

**Quality Gate**:
- ✓ <5% null values
- ✓ <1% duplicates
- ✓ All validations pass

---

### Stage 2B: Refined (Privacy-Compliant)

**Purpose**: Apply privacy rules for FERPA compliance, enable authorized analysis

**Transformations Applied**:

1. **Deterministic Hashing**
   - `student_id: STU00123` → `hashed_student_id: a7f3e8d2c1...`
   - Same input = same hash (consistent across time)
   - Allows authorized users to link records
   - Cannot reverse to original value

2. **Irreversible Masking**
   - `first_name: John` → `first_name: Jo****`
   - `phone: 555-1234` → `phone: 555-****`
   - Cannot recover original information

3. **No-op (Unchanged)**
   - `grade_level: 9` → `grade_level: 9`
   - Non-sensitive fields pass through

4. **Aggregation**
   - Group by hashed student ID
   - Calculate metrics: attendance_rate, grade_average
   - Suppress small groups (<5 students)

**Schema Example**:
```
Stage 2B Student Record:
{
  hashed_student_id: "a7f3e8d2c1b45e9f2a3b",
  first_name: "Jo****",
  last_name: "Sm****",
  grade_level: 9,
  enrollment_status: "Active",
  _modified_date: 2026-01-20 10:30:00
}
```

**Access Control**:
- Role-based views (teachers, admins, researchers)
- Data row filtering by organizational unit
- Query logging for audit

---

### Stage 3: Analytics (Clean & Ready)

**Purpose**: Denormalized, feature-rich data for dashboards and reports

**Transformations Applied**:

1. **Entity Joining**
   ```
   student_performance = 
     students JOIN enrollment ON hashed_student_id
     JOIN courses ON course_id
     JOIN attendance ON hashed_student_id
   ```

2. **Feature Engineering**
   - `attendance_rate = present_days / total_days`
   - `grade_average = AVG(all_assignment_grades)`
   - `engagement_score = (attendance * 0.3) + (grades * 0.7)`
   - `trend_flag = CASE WHEN grade_trend > 5 THEN 'improving' ...`
   - `at_risk_flag = CASE WHEN grade < 60 OR attendance < 0.80 THEN true ...`

3. **Table Creation**
   - `student_performance`: Per-student metrics
   - `course_summary`: Per-course aggregates
   - `teacher_view`: Teacher's course roster with metrics
   - `district_summary`: District KPIs

**Schema Example**:
```
Stage 3 Student Performance Record:
{
  hashed_student_id: "a7f3e8d2c1b45e9f2a3b",
  course_id: "MATH101",
  course_name: "Algebra I",
  final_grade: 85.5,
  attendance_rate: 0.95,
  grade_average: 87.2,
  engagement_score: 0.87,
  at_risk_flag: false,
  trend_flag: "improving",
  cohort_year: 2024,
  school_id: "SCH001"
}
```

**Use Cases**:
- Dashboard widgets
- Analytics queries
- Machine learning models
- Performance reports

---

## Data Model

### Core Entities

#### Students
```
Attributes (27):
- Identity: student_id, first_name, last_name, date_of_birth
- Demographics: gender, ethnicity, grade_level
- Enrollment: enrollment_status, school_id, district_id, cohort_year
- Special Programs: special_education, english_learner, economically_disadvantaged, 
                    homeless_status, foster_care_status, military_family
- Contact: phone_number, email_address, address (line1, city, state, zip)
- Metadata: _sis_modified_date, _load_timestamp

Relationships:
- 1 student : many enrollments
- 1 student : many attendance records
- 1 student : many academic_records
```

#### Courses
```
Attributes (18):
- Identity: course_id, course_code, course_name
- Description: course_description, subject_area
- Scheduling: grade_level, term, start_date, end_date
- Capacity: max_enrollment, min_enrollment
- Instructor: teacher_id
- Status: status (active, archived, etc.)
- Type: course_type (regular, honors, AP, etc.)
- Value: credit_value
- Metadata: _sis_modified_date

Relationships:
- 1 course : many enrollments
- 1 course : 1 teacher (typically)
- 1 course : many attendance records
```

#### Enrollment
```
Attributes (23):
- Identity: enrollment_id, student_id, course_id
- Timing: enrollment_date, completion_date, term
- Academic: final_grade_letter, final_grade_numeric, credits_earned, credits_attempted
- Attendance: attendance_days, absence_count, tardy_count
- Status: enrollment_status (enrolled, completed, dropped, etc.)
- Metadata: _sis_modified_date

Relationships:
- many enrollments : 1 student
- many enrollments : 1 course
```

#### Attendance
```
Attributes (21):
- Identity: attendance_id, student_id, school_id, course_id
- Daily: attendance_date, status (present, absent, tardy, excused)
- Tracking: cumulative_days, cumulative_absences, cumulative_tardies
- Patterns: attendance_rate, absence_pattern
- Metadata: _sis_modified_date

Relationships:
- many records : 1 student
- many records : 1 course
```

#### Academic_Records
```
Attributes (24):
- Identity: record_id, student_id, course_id
- Assignment: assignment_name, assignment_date, points_possible, points_earned
- Standards: standard_code, proficiency_level
- Assessment: test_name, test_date, test_score, test_type
- Grades: assignment_grade, term_grade, final_grade
- Mastery: mastery_level (not_demonstrated, developing, proficient, advanced)
- Metadata: _sis_modified_date

Relationships:
- many records : 1 student
- many records : 1 course
```

---

## Configuration Files

### extraction_config.yaml

Controls SIS connection and data extraction:

```yaml
sis:
  system: powerschool              # Vendor identification
  host: ps.school.edu              # Connection host
  port: 1433
  driver: mssql+pyodbc
  database: pssis
  username: ${SIS_USER}            # From environment
  password: ${SIS_PASSWORD}
  
  query: |                         # SQL extraction query
    SELECT StudentID as student_id,
           FirstName as first_name,
           ...
    FROM STUDENTS
    WHERE ModifyDate > ?
  
  batch_date_format: "%Y-%m-%d"   # Date format for parameterized queries
  connection_timeout: 30

output:
  folder: sis_exports/
  format: csv                      # Output format
  csv:
    delimiter: ","
    encoding: utf-8
    include_header: true

database:
  host: ${DB_HOST}                # Target data lake
  port: 5432
  driver: postgresql
  database: data_lake

batch:
  mode: delta                      # delta/additive/snapshot
  key_columns: [student_id]        # For delta deduplication
  batch_date_column: _sis_modified_date
  since_date: yesterday            # For delta extraction
```

### transformation_config.yaml

Controls field mapping, validation, and pseudonymization:

```yaml
entities:
  students:
    source_table: dbo.Students
    
    mappings:                      # SIS column -> standard schema
      student_id: StudentNumber
      first_name: FirstName
      # ... (27 fields total)
    
    type_mappings:                 # Data type specifications
      student_id: VARCHAR(20)
      grade_level: INT
      # ... 
    
    pseudonymization:              # Privacy rules for Stage 2B
      student_id: hash             # Deterministic
      first_name: mask             # Irreversible
      grade_level: no-op           # Unchanged
    
    validation:                    # Quality rules for Stage 2A
      null_check: [student_id, first_name, last_name]
      unique_check: [student_id]
      range_check:
        grade_level: [0, 16]

quality:
  max_null_percent: 0.05           # <5% nulls allowed
  max_duplicate_percent: 0.01      # <1% duplicates
  min_record_count: 100
  max_error_percent: 0.02          # <2% validation errors
```

---

## Pipeline Orchestration

Five JSON templates define the transformation pipeline:

### 00_extract_sis.json
- Connect to SIS system
- Execute extraction query
- Export to CSV/JSON
- Log metrics

### 01_land_stage1.json
- Read extracted files
- Organize by date partition
- Add metadata
- Store in Stage 1

### 02_transform_stage2a.json
- Load Stage 1 data
- Apply field mappings
- Convert data types
- Validate against rules
- Deduplicate records
- Check quality thresholds
- Store in Stage 2A

### 03_refine_stage2b.json
- Load Stage 2A data
- Hash/mask/no-op by rules
- Aggregate metrics
- Create role-based views
- Store in Stage 2B

### 04_aggregate_stage3.json
- Load Stage 2B data
- Join entities
- Compute features
- Create analytics tables
- Final validation
- Store in Stage 3

---

## Security & Privacy

### FERPA Compliance

**Family Educational Rights and Privacy Act (FERPA)**:
- Protects student educational records
- Requires explicit consent for data sharing
- Allows school officials access for legitimate educational interests

**Implementation**:
- Stage 1: Raw data (restricted to technical admins)
- Stage 2A: Normalized data (restricted to authorized staff)
- Stage 2B: Pseudonymized data (limited role access)
- Stage 3: Analytics data (teacher/admin access with filters)

### Pseudonymization Strategy

**Hash (Deterministic)**:
- Use consistent seed across all runs
- Allows authorized users to link records across datasets
- Example: student_id "STU00123" → "a7f3e8d2c1b45e9f2a3b"

**Mask (Irreversible)**:
- One-way transformation
- Cannot recover original value
- Example: "John Smith" → "Jo**** Sm****"

**No-op (Unchanged)**:
- Non-sensitive data passes through
- Grades, codes, status remain unchanged

### Access Control

**Role-Based Access Control (RBAC)**:
- **Technician**: Stage 1 & 2A (for support)
- **Teacher**: Stage 2B & 3 (filtered by own courses)
- **Administrator**: Stage 2B & 3 (full district access)
- **Researcher**: Stage 2B & 3 (anonymized aggregates only)

**Implementation**:
- Database users/roles
- Row-level security (RLS)
- Query-level access control
- Audit logging

---

## Performance Considerations

### Data Volume

**Typical SIS Dataset**:
- Students: 10,000-100,000+
- Courses: 1,000-5,000+
- Enrollments: 50,000-500,000+
- Attendance: 1M-10M+ records

**Stage 1→2A Processing**:
- 100K student records: ~5-10 minutes
- 500K enrollment records: ~30-60 minutes

**Optimization Strategies**:
- Batch processing (process by date range)
- Parallel processing (by entity type)
- Index on join keys and filters
- Partitioning by date

### Storage

**Typical Space Usage**:
- Stage 1: 2-5x raw export size
- Stage 2A: 1-2x Stage 1 (normalized)
- Stage 2B: 0.8-1x Stage 2A (some aggregation)
- Stage 3: 0.5-0.8x Stage 2B (denormalized)

**Example**: 1GB SIS extract
- Stage 1: ~3GB
- Stage 2A: ~3GB
- Stage 2B: ~2.5GB
- Stage 3: ~2GB
- **Total**: ~10.5GB for full pipeline

---

## Monitoring & Alerting

### Key Metrics

- **Extraction**: Record count, duration, size, success rate
- **Validation**: Null %, duplicates %, error %
- **Quality**: Pass/fail by entity, threshold compliance
- **Performance**: Pipeline duration by stage

### Alert Thresholds

- ⚠️ Warning: Quality metrics >80% of threshold
- 🚨 Error: Quality metrics exceed threshold
- 📊 Info: Successful pipeline completion

---

## Troubleshooting Guide

See `TROUBLESHOOTING.md` for common issues:

- Connection failures
- Data validation errors
- Type conversion problems
- Privacy rule conflicts
- Performance degradation
- Storage space issues

---

**Last Updated**: January 26, 2026  
**Version**: 1.0  
**Framework**: OSS (Open Source Education)
