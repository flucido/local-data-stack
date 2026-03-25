# Metadata & Schema System

This directory contains the comprehensive metadata schema definitions for the Education Analytics Framework. Each schema file defines the structure, data types, pseudonymization rules, and descriptions for key education entities.

## Overview

The metadata system is organized into entity-specific schema files, each defining the attributes, data types, privacy rules, and column descriptions needed for education data pipelines. This enables:

- **Consistent data governance** across all education analytics implementations
- **Automated privacy enforcement** through metadata-driven pseudonymization rules
- **Clear documentation** of what data is collected and how it's protected
- **Data dictionary generation** for stakeholder communication
- **Validation automation** through schema-aware quality checks

## Schema Files

### 1. `schema_students.csv`

**Purpose**: Core student demographic and enrollment information

**Key Attributes** (27 total):
- **Identifiers**: student_id (hashed), school_id, district_id
- **Demographics**: first_name, last_name, date_of_birth, gender, ethnicity, grade_level
- **Status Indicators**: enrollment_status, special_education, english_learner, economically_disadvantaged
- **Special Populations**: homeless_status, foster_care_status, military_family
- **Contact**: phone_number (masked), email_address (masked), address fields (masked)
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: student_id, date_of_birth (enables linkage while hiding PII)
- `mask`: name fields, contact information (irreversible one-way transformation)
- `no-op`: demographics, status fields, cohort year (retain for analysis)

**Example Usage**:
```python
from oss_framework import MetadataManager

metadata = MetadataManager('oss_framework/metadata/metadata_combined.csv')
student_rules = metadata.get_privacy_rules('students')
# Returns: {'student_id': 'hash', 'first_name': 'mask', ...}
```

---

### 2. `schema_courses.csv`

**Purpose**: Course catalog, scheduling, and instructor information

**Key Attributes** (19 total):
- **Identifiers**: course_id, course_code, school_id
- **Course Details**: course_name, course_description, subject_area, grade_level
- **Enrollment**: max_enrollment, min_enrollment, credit_value
- **Classification**: course_type (regular/honors/AP/IB/CTE), term
- **Scheduling**: start_date, end_date, status
- **Instructor**: teacher_id (hashed)
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: teacher_id (prevents direct identification of staff)
- `no-op`: all other fields (course information is not sensitive)

**Rationale**: Course information itself is generally not sensitive, but instructor identifiers are masked to prevent profiling individual teachers. Course structure, timing, and enrollment limits are retained for capacity planning and curriculum analysis.

---

### 3. `schema_enrollment.csv`

**Purpose**: Student-course relationships, grades, and completion tracking

**Key Attributes** (23 total):
- **Link Fields**: enrollment_id, student_id (hashed), course_id, school_id, term
- **Dates**: enrollment_date, completion_date
- **Status & Grades**: enrollment_status, final_grade_letter, final_grade_numeric
- **Credits**: credits_earned, credits_attempted, weighted_gpa_impact
- **Attendance**: attendance_days, absence_count, tardy_count, excused/unexcused splits
- **Flags**: engagement_flag, academic_risk_flag (computed indicators)
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: student_id (links to student table via hash)
- `no-op`: academic data, grades, attendance (core for analytics)

**Rationale**: Academic performance data is retained because it's essential for identifying at-risk students and tracking progress. Student ID is hashed to prevent column-level re-identification. Computed risk flags are pre-calculated for easy filtering.

**Example**:
```csv
enrollment,enrollment_id,VARCHAR,no-op
enrollment,student_id,VARCHAR,hash
enrollment,final_grade_numeric,FLOAT,no-op
enrollment,academic_risk_flag,BOOLEAN,no-op
```

---

### 4. `schema_engagement_events.csv`

**Purpose**: LMS and platform activity tracking for student engagement analysis

**Key Attributes** (21 total):
- **Link Fields**: event_id, student_id (hashed), course_id, school_id
- **Event Details**: event_timestamp, event_type, resource_id, resource_name, resource_type
- **Interaction Metrics**: duration_seconds, interaction_depth, time_on_task
- **Device/Platform**: device_type, platform, lms_session_id
- **Privacy**: ip_address_hash, user_agent_hash
- **Quality Flags**: content_interaction_flag, submission_quality_score
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: student_id, ip_address_hash, user_agent_hash (prevents location/device re-identification)
- `no-op`: all other fields (engagement patterns are non-sensitive)

**Event Types**:
- `page_view`: Viewing course/assignment pages
- `assignment_submit`: Submitting assignments
- `quiz_attempt`: Taking quizzes
- `discussion_post`: Posting in discussions
- `resource_download`: Downloading materials
- `video_watch`: Watching embedded video

**Example Event**:
```json
{
  "event_id": "evt_12345",
  "student_id": "hash_xyz",           // Hashed
  "event_type": "assignment_submit",
  "duration_seconds": 1800,           // 30 minutes
  "interaction_depth": "submit",
  "submission_quality_score": 85
}
```

---

### 5. `schema_attendance.csv`

**Purpose**: Daily attendance tracking and chronicity indicators

**Key Attributes** (22 total):
- **Link Fields**: attendance_id, student_id (hashed), school_id, course_id
- **Date & Time**: attendance_date, checkin_time, checkout_time
- **Presence**: is_present, absence_type, absence_reason
- **Timing**: tardy_flag, early_departure_flag, partial_absence_duration
- **Aggregates**: absence_count (term-level), chronic_absence_flag
- **Trends**: attendance_pattern (improving/declining/stable/at_risk)
- **Follow-up**: makeup_assignment_required, parent_notification_sent
- **Context**: period_or_class, teacher_id (hashed)
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: student_id, teacher_id
- `no-op`: attendance data (used for intervention)

**Absence Types**:
- `excused`: Parent-excused or legitimate absence
- `unexcused`: Truancy
- `medical`: Medical appointment (with documentation)
- `OSS`: Out-of-school suspension
- `ISS`: In-school suspension
- `field_trip`: School-authorized field trip

**Use Cases**:
- Identify chronically absent students (>10% absence rate)
- Track patterns (e.g., Monday/Friday absences)
- Trigger parent outreach at thresholds
- Correlate with academic performance and engagement

---

### 6. `schema_academic_records.csv`

**Purpose**: Assignment-level performance data, grades, and formative assessments

**Key Attributes** (23 total):
- **Link Fields**: record_id, student_id (hashed), course_id, school_id, term
- **Assignment**: assignment_id, assignment_name, assignment_type, assignment_due_date
- **Submission**: assignment_submission_date, submission_status, late_days
- **Performance**: points_earned, points_possible, assignment_grade_percent, assignment_grade_letter
- **Feedback**: on_time_flag, teacher_id (hashed), feedback_provided, feedback_date
- **Assessment**: rubric_score, mastery_level (novice/developing/proficient/advanced)
- **Metadata**: _loaded_date, _updated_date

**Pseudonymization Rules**:
- `hash`: student_id, teacher_id
- `no-op`: grades, performance metrics, mastery assessments

**Assignment Types**:
- `homework`: Practice assignments
- `quiz`: Formative quizzes
- `exam`: Summative assessments
- `project`: Multi-part projects
- `discussion`: Discussion forum posts
- `participation`: Class participation

**Mastery Levels**:
- `novice`: <60% mastery (below standard)
- `developing`: 60-79% (approaching standard)
- `proficient`: 80-94% (meets standard)
- `advanced`: 95-100% (exceeds standard)

---

## Combined Metadata File

**`metadata_combined.csv`**: Master metadata reference consolidating all six schemas

- **Total Records**: 132 attributes across 6 entities
- **Organization**: Sorted by Entity name, then Attribute name alphabetically
- **Use Case**: Single source of truth for validation, documentation, and automation

**Command to Generate**:
```bash
cat schema_*.csv | grep -v "^Entity," | sort -t',' -k1,1 -k2,2 > temp
head -1 schema_students.csv | cat - temp > metadata_combined.csv
```

---

## Pseudonymization Strategy

### Hash (One-Way, Linkable)
**Applied to**: student_id, teacher_id, date_of_birth, ip_address, user_agent

**Characteristics**:
- Deterministic (same input = same hash)
- One-way (cannot be reversed)
- Enables record linkage across tables
- Can create lookup tables for authorized users
- Suitable for: identifiers that need consistency

**Implementation**:
```python
import hashlib

def hash_value(value: str) -> str:
    """Generate SHA-256 hash of value"""
    return hashlib.sha256(value.encode()).hexdigest()

# student_id "STU001" always hashes to same value
hashed_id = hash_value("STU001")  # "abc123def456..."
```

### Mask (One-Way, Non-Linkable)
**Applied to**: names, phone numbers, email addresses, addresses

**Characteristics**:
- Irreversible
- Different rules per field type
- Cannot be reversed to original value
- Suitable for: direct PII that doesn't need linkage

**Implementation**:
```python
def mask_name(name: str) -> str:
    """Mask name by replacing with initial + asterisks"""
    return name[0] + "***" if name else None

def mask_phone(phone: str) -> str:
    """Mask phone by keeping area code, masking rest"""
    return phone[:3] + "***" + phone[6:] if phone else None

def mask_email(email: str) -> str:
    """Mask email address"""
    user, domain = email.split("@")
    return user[0] + "***@" + domain if email else None
```

### No-Op (No Pseudonymization)
**Applied to**: grades, demographics, status flags, course information, engagement metrics

**Characteristics**:
- Data retained as-is
- Non-sensitive or inherently aggregate
- Essential for analytics

**Rationale Examples**:
- Grades aren't PII (student hash + grade is useless without context)
- Demographic categories (grade level, ethnicity) are aggregation dimensions
- Engagement metrics (time on task) are non-identifying
- Course codes don't identify individuals

---

## Using Metadata in Your Code

### 1. Load Metadata Manager

```python
from oss_framework import MetadataManager

# Load combined metadata
metadata = MetadataManager('oss_framework/metadata/metadata_combined.csv')

# Get all attributes for an entity
students = metadata.get_entity_attributes('students')
# Returns: ['student_id', 'first_name', 'last_name', ...]

# Get privacy rules for an entity
rules = metadata.get_privacy_rules('students')
# Returns: {
#   'student_id': 'hash',
#   'first_name': 'mask',
#   'grade_level': 'no-op',
#   ...
# }
```

### 2. Generate Data Dictionary

```python
# Generate markdown documentation
markdown_doc = metadata.generate_data_dictionary(format='markdown')
with open('DATA_DICTIONARY.md', 'w') as f:
    f.write(markdown_doc)

# Generate HTML for web viewing
html_doc = metadata.generate_data_dictionary(format='html')
```

### 3. Validate Data Against Schema

```python
from oss_framework import DataTransformer

transformer = DataTransformer(metadata)

# Validate enrollment data
validation_result = transformer.validate_schema(
    data=enrollment_df,
    entity='enrollment'
)

if not validation_result['valid']:
    print(validation_result['errors'])
```

### 4. Apply Pseudonymization

```python
from oss_framework import Pseudonymizer

pseudonymizer = Pseudonymizer(metadata)

# Apply privacy rules to student data
anonymized_students = pseudonymizer.pseudonymize(
    data=students_df,
    entity='students'
)
```

---

## Examples & Test Cases

### Example 1: Identify At-Risk Students

```python
# Load enrollment and attendance data
enrollment = metadata.get_entity_attributes('enrollment')
attendance = metadata.get_entity_attributes('attendance')

# Query for students with academic risk flags + chronic absences
at_risk = df[
    (df['academic_risk_flag'] == True) &
    (df['chronic_absence_flag'] == True)
]

# Safe to share: hashed student_id + risk indicators
at_risk[['student_id', 'academic_risk_flag', 'attendance_pattern']].to_csv(
    'at_risk_for_intervention.csv'
)
```

### Example 2: Course Engagement Dashboard

```python
# Group engagement events by course
engagement_by_course = engagement_df.groupby('course_id').agg({
    'event_id': 'count',  # Total events
    'duration_seconds': 'mean',  # Avg time
    'student_id': 'nunique'  # Unique students
})

# Safe to share: no student identifiers, only aggregates
engagement_dashboard = engagement_by_course.reset_index()
engagement_dashboard.to_csv('course_engagement_summary.csv')
```

### Example 3: Academic Performance Trends

```python
# Calculate grade trends by assignment type
grades_by_type = academic_records_df.groupby('assignment_type').agg({
    'assignment_grade_percent': ['mean', 'std', 'count'],
    'mastery_level': lambda x: (x == 'proficient').sum() / len(x)
})

# Safe to publish: aggregated, no individual identifiers
grades_by_type.to_csv('academic_performance_by_assignment_type.csv')
```

---

## Metadata Dictionary Structure

Each CSV file follows this structure:

```
Entity          | Attribute          | DataType  | Pseudonymization | Description
----------------|------------------|-----------|------------------|------------------------------------------
students        | student_id        | VARCHAR   | hash             | Unique student identifier from SIS
students        | first_name        | VARCHAR   | mask             | Student first name
students        | grade_level       | INT       | no-op            | Current grade level (K-12 or 1-16)
...
```

### Column Definitions

- **Entity**: Logical entity/table name (e.g., students, courses, enrollment)
- **Attribute**: Column/field name within entity
- **DataType**: SQL/database data type (VARCHAR, INT, DATE, TIMESTAMP, FLOAT, BOOLEAN)
- **Pseudonymization**: Privacy rule to apply
  - `hash`: One-way hashing (SHA-256)
  - `mask`: One-way masking specific to field type
  - `no-op`: No transformation (retain as-is)
- **Description**: Human-readable explanation and business logic

---

## Data Type Reference

| Type | Examples | Use Cases |
|------|----------|-----------|
| **VARCHAR** | Names, codes, descriptions | Categorical, identifiers |
| **INT** | Grade levels, counts, minutes | Whole numbers |
| **FLOAT** | GPA, percentages, scores | Decimal values |
| **DATE** | Birthdate, enrollment_date | Dates without time |
| **TIMESTAMP** | Event times, load dates | Dates with time precision |
| **BOOLEAN** | Flags, yes/no indicators | Binary attributes |

---

## Privacy Considerations

### PII & Sensitive Data

Protected identifiers:
- Names (first, last, middle)
- Date of birth
- Contact info (phone, email, address)
- Teacher identifiers
- IP addresses
- Device signatures

**All are hashed or masked in this schema.**

### Non-Sensitive Data

Safe for analysis:
- Grades and academic performance
- Demographic categories (not individual identifiers)
- Engagement metrics
- Attendance patterns (aggregated)
- Course enrollments

**All retained as-is in this schema.**

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial metadata system with 6 core education entities |

---

## Related Documentation

- **Data Lake Architecture**: `../docs/tech_docs/data_lake_architecture.md`
- **Pipeline Orchestration**: `../pipeline_templates/README.md`
- **Utilities Library**: `../utilities/oss_framework/__init__.py`
- **Getting Started**: `../docs/getting_started.md`

---

## Support & Questions

For questions about:
- **Schema design**: See entity-specific documentation above
- **Privacy rules**: Consult Pseudonymization Strategy section
- **Implementation**: See Using Metadata in Your Code section
- **Validation**: Check Examples & Test Cases section
