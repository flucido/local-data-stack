# SQL Templates and Query Reference

## Overview

This directory contains SQL templates and queries for the SIS data pipeline. Queries are organized by stage to support data validation, transformation, and analytics.

### File Organization

```
queries/
├── 01_stage1_validation.sql        Stage 1: Raw data quality checks
├── 02_stage2a_normalized_views.sql Stage 2A: Normalized schema views
├── 03_stage2b_privacy_refined_views.sql Stage 2B: De-identified views with pseudonymization
├── 04_stage3_analytics_views.sql   Stage 3: Aggregated analytics views
└── README.md                       This file
```

---

## Stage 1: Raw Data Validation

**File**: `01_stage1_validation.sql`

**Purpose**: Validate data quality in the landing zone before transformation

**Key Queries**:

1. **Table Structure Validation**
   - Verify all required tables exist
   - Check column names, types, and nullability
   - Ensure database schema matches expectations

2. **Record Count and Distribution**
   - Summary of table sizes
   - Distribution by enrollment status and grade level
   - Identify missing data patterns

3. **NULL Value Detection**
   - Find NULL values in critical fields
   - Calculate percentage of missing data
   - Identify data quality issues early

4. **Uniqueness Constraints**
   - Check for duplicate student IDs
   - Verify unique course IDs
   - Detect duplicate enrollments

5. **Data Type and Format Validation**
   - Invalid dates (future dates, out-of-range years)
   - Invalid GPA values (outside 0.0-4.0 range)
   - Invalid grade codes
   - Malformed text fields

6. **Referential Integrity**
   - Orphaned enrollment records (students don't exist)
   - Orphaned course references
   - Missing relationships

7. **Enrollment Status Consistency**
   - Withdrawn students with future withdrawal dates
   - Active students with very old enrollment dates
   - Inconsistent status/grade_level combinations

8. **Date Range Validation**
   - Attendance dates outside expected range
   - Academic records with submission before assignment
   - Date relationships (enrollment before graduation)

9. **Numeric Ranges and Outliers**
   - Attendance rates outside 0.0-1.0
   - Grade percentages outside 0-100
   - Invalid credit hours

10. **Privacy and Sensitivity**
    - Check for valid email formats
    - Check for valid phone formats
    - Check for Social Security numbers

11. **Summary Quality Report**
    - Overall data quality scorecard
    - PASS/WARNING/CRITICAL status by table
    - JSON export for automated monitoring

**Usage**:
```bash
# Connect to database and run validation
psql -h sis.example.com -U extract_user -d sis_prod -f 01_stage1_validation.sql

# Or export results to file
psql -h sis.example.com -U extract_user -d sis_prod -f 01_stage1_validation.sql -o validation_report.txt

# Run specific query
psql -d sis_prod -c "SELECT enrollment_status, COUNT(*) FROM students GROUP BY enrollment_status;"
```

---

## Stage 2A: Normalized Schema Views

**File**: `02_stage2a_normalized_views.sql`

**Purpose**: Transform raw data into standardized, usable schema

**Views Created**:

### 1. students_normalized
- Standardized field names and types
- Calculated fields: birth_year, years_enrolled, age
- Consistent enum values for status, gender, ethnicity, program
- Validation: invalid dates coerced to NULL, invalid GPAs handled

**Key Transformations**:
```
Enrollment Status:  A→Active, G→Graduated, W→Withdrawn, T→Transferred
Gender:            M→Male, F→Female, O→Other, N→Not Specified
Ethnicity:         HISP→Hispanic, AA→African American, W→White, etc.
Academic Program:  CP→College Prep, VOC→Vocational, STEM, IB
GPA:               Validated 0.0-4.0, rounded to 2 decimals
```

### 2. courses_normalized
- Standard course information
- Calculated fields: capacity_percent, grade_level ranges
- Consistent course type values
- Instructor info preserved for Stage 2A validation

**Key Transformations**:
```
Course Type:       AP→Advanced Placement, HON→Honors, REG→Regular, REM→Remedial
Grade Level:       Validated 0-12, invalid values default to 0 or 12
Credit Hours:      Validated 0-10, invalid default to 1.0
Capacity Percent:  Calculated as (enrollment_count / capacity) * 100
```

### 3. enrollment_normalized
- Standardized grade values (A, B, C, D, F, I, W, P, NP)
- Calculated fields: submission_timeliness, failure flags
- Engagement metrics calculated
- Performance indicators computed

**Key Transformations**:
```
Letter Grade:      Validated against approved list, invalid→unknown
Grade Percent:     Validated 0-100, out-of-range→NULL
GPA Contribution:  Validated 0.0-4.0, invalid→NULL
Assignment Rate:   Validated 0-1.0, rounded to 3 decimals
Timeliness:        Calculated based on submission vs assignment date
```

### 4. attendance_normalized
- Date generalized to week level for privacy
- Status standardized (Present, Absent, Tardy, Excused, Unexcused)
- Calculated: attendance_rate, risk level
- Warning levels: Green→Low Risk, Yellow→Medium, Red→High

**Key Transformations**:
```
Attendance Date:   Generalized to DATE_TRUNC('week', ...)
Status Codes:      P→Present, A→Absent, T→Tardy, E→Excused, U→Unexcused
Rates:             Validated 0.0-1.0, null if outside range
Warning Level:     GREEN/YELLOW/RED based on thresholds
```

### 5. academic_records_normalized
- Standardized assignment types
- Calculated: submission timeliness, late day counts
- Mastery levels standardized
- Learning outcome tracking

**Key Transformations**:
```
Mastery Level:     A→Advanced, P→Proficient, D→Developing, B→Beginning
Score Percent:     Validated 0-100, invalid→NULL
Timeliness:        Calculated: On Time, Late<3 days, Late<7 days, Very Late
Retakes:           Counted and compared to original score
```

**Usage**:
```bash
# Run all normalizations
psql -d stage_2a -f 02_stage2a_normalized_views.sql

# Query normalized data
psql -d stage_2a -c "SELECT grade_level, COUNT(*) FROM stage_2a.students_normalized GROUP BY grade_level;"

# Check transformation completeness
psql -d stage_2a -f 02_stage2a_normalized_views.sql | grep "Verification"
```

---

## Stage 2B: Privacy-Refined Views

**File**: `03_stage2b_privacy_refined_views.sql`

**Purpose**: Apply pseudonymization rules (hash, mask, no-op) for FERPA compliance

**Privacy Functions Created**:

### privacy.hash_pii(text) → text
- **Purpose**: Deterministic, one-way pseudonymization
- **Algorithm**: SHA-256 with district salt
- **Output**: 64-character hex string
- **Characteristics**: Same input always produces same output (linkable)
- **Applied To**: student_id, teacher_id, date_of_birth, SSN
- **Example**: "S12345" → "a3c9f7e2b1d4c8a5f6e9b2c1d4e7f8a9"

### privacy.mask_text(text, visible_chars, mask_char) → text
- **Purpose**: Irreversible, non-deterministic pseudonymization
- **Algorithm**: Show first N chars, replace rest with mask character
- **Output**: Masked string (e.g., "John" → "Jo****")
- **Characteristics**: Cannot recover original, each masking unique
- **Applied To**: first_name, last_name, email, phone, address
- **Example**: "john.smith@example.com" → "jo**@ex****.***"

### privacy.mask_email(text) → text
- **Purpose**: Domain-aware email masking
- **Algorithm**: Mask local and domain separately
- **Output**: "jo**@ex****.***"
- **Applied To**: email fields

### privacy.mask_phone(text) → text
- **Purpose**: Phone number masking
- **Algorithm**: Show area code + exchange, hide local
- **Output**: "+1-555-****"
- **Applied To**: phone fields

**Views Created**:

### 1. students_refined
**Pseudonymized Fields**:
- `student_id_hashed`: SHA-256(student_id)
- `first_name_masked`: Show first 2, mask rest
- `last_name_masked`: Show first 1, mask rest
- `dob_hashed`: SHA-256(date_of_birth)
- `email_masked`: Mask local + domain
- `phone_masked`: Show area code, mask local
- `address_masked`: Completely masked

**Preserved Fields**:
- grade_level, enrollment_status, gender, ethnicity
- special_education, english_learner, free_reduced_lunch
- gpa, enrollment_date

**Privacy Classification**: FERPA Compliant

### 2. courses_refined
**Pseudonymized Fields**:
- `instructor_id_hashed`: SHA-256(instructor_id)
- `instructor_name_masked`: Show first 1, mask rest
- `instructor_email_masked`: Domain-aware mask

**Preserved Fields**:
- course_name, course_code, department, subject
- credit_hours, grade_level_min/max
- capacity, enrollment, meeting_schedule

**Privacy Classification**: FERPA Compliant

### 3. enrollment_refined
**Pseudonymized Fields**:
- `enrollment_id_hashed`: SHA-256(enrollment_id)
- `student_id_hashed`: SHA-256(student_id)

**Preserved Fields**:
- course_id, term, completion_status
- grades (letter, percent, gpa_contribution, weighted)
- engagement metrics (assignment_completion, participation)
- accommodation flags

**Privacy Classification**: FERPA Compliant

### 4. attendance_refined
**Pseudonymized Fields**:
- `attendance_id_hashed`: SHA-256(attendance_id)
- `student_id_hashed`: SHA-256(student_id)

**Preserved Fields**:
- attendance_week (generalized from daily date)
- attendance_status, reason_category
- attendance_rate, cumulative_absence_rate
- warning_level, chronically_absent flag

**Privacy Classification**: FERPA Compliant

### 5. academic_records_refined
**Pseudonymized Fields**:
- `record_id_hashed`: SHA-256(record_id)
- `student_id_hashed`: SHA-256(student_id)

**Preserved Fields**:
- course_id, assignment_name, assignment_type
- mastery_level, score_percent
- submission_timeliness, late_day_count
- remediation/enrichment offered flags

**Privacy Classification**: FERPA Compliant

**Linked Views**:
- `student_enrollment_view`: Join students, enrollment, courses, attendance using hashed IDs
- `course_performance_summary`: Aggregated course metrics (no individual records)

**Audit Table**:
- `privacy_audit_log`: Track all Stage 2B data access for compliance

**Usage**:
```bash
# Create privacy-refined views
psql -d stage_2b -f 03_stage2b_privacy_refined_views.sql

# Query de-identified data
psql -d stage_2b -c "SELECT student_id_hashed, grade_level, gpa FROM stage_2b.students_refined;"

# Verify pseudonymization
psql -d stage_2b -f 03_stage2b_privacy_refined_views.sql | grep "Verification"

# Check audit log
psql -d stage_2b -c "SELECT * FROM stage_2b.privacy_audit_log ORDER BY accessed_timestamp DESC LIMIT 10;"
```

---

## Stage 3: Analytics Views

**File**: `04_stage3_analytics_views.sql`

**Purpose**: Fully de-identified aggregates for dashboards and public reporting

**Views Created** (Aggregated Only - No Individual Records):

### 1. district_summary
- Active students, graduates, withdrawn
- Students by grade level (JSON)
- Special program counts
- District average GPA, attendance rate
- Chronically absent student count
- Total courses and enrollments

### 2. grade_level_performance
- Student count per grade
- Demographics: % special ed, % ELL
- Academic performance: avg/min/max GPA
- Grade distribution: high achievers, struggling, failure rate
- Attendance metrics: avg rate, chronic absence, high-risk count

### 3. department_performance
- Courses per department/subject
- Total enrollments by subject
- Grade distribution
- Intervention flag percentage
- Engagement: avg assignment completion, participation score

### 4. term_trends
- Enrollments per term
- Courses offered per term
- Average grade and GPA per term
- Failing enrollments per term
- Chronically absent students per term

### 5. at_risk_aggregates
- Attendance risk: chronically absent count
- Academic risk: flagged for intervention, GPA < 2.0
- Demographic indicators: special ed, ELL percentages
- All reported as counts and percentages, no names

### 6. course_utilization
- Course capacity and enrollment
- Demand levels: Over Capacity, High Demand, Good, Moderate, Low
- Performance in course: avg grade, achievement distribution
- Failing students per course

### 7. advanced_track_performance
- Comparison: AP vs Honors vs Regular track
- Grade distribution by track
- Achievement metrics by track
- GPA contribution by track

### 8. special_programs_impact
- Effectiveness of special programs
- Special Ed: avg GPA, attendance, intervention rate
- ELL: same metrics
- FRPL: same metrics
- Cross-program analysis

### 9. competency_mastery_trends
- Learning outcome tracking
- Mastery level distribution: Advanced, Proficient, Developing, Beginning
- Remediation and enrichment needed
- Progress on standards

### 10. data_quality_summary
- Data completeness percentage
- Records with complete enrollment, attendance, grades
- Overall data quality assessment

**Key Principles**:
- All individual records are aggregated
- Minimum group sizes enforced (no small groups that could identify individuals)
- No personal identifiers (names, IDs, dates)
- Geographic data generalized (grade level, not zip code)
- Suitable for public dashboards and research reports

**Usage**:
```bash
# Create analytics views
psql -d stage_3 -f 04_stage3_analytics_views.sql

# Query district summary
psql -d stage_3 -c "SELECT * FROM stage_3.district_summary;"

# Export term trends for dashboard
psql -d stage_3 -c "SELECT * FROM stage_3.term_trends;" -o term_trends.csv

# Check mastery trends
psql -d stage_3 -c "SELECT * FROM stage_3.competency_mastery_trends ORDER BY advanced_percent DESC LIMIT 20;"
```

---

## Best Practices

### 1. Query Performance
- Use indexes: already created on key columns (IDs, status, dates, grades)
- Filter early: use WHERE clauses in Stage 1 validation
- Aggregate efficiently: Stage 3 views pre-aggregate for dashboard speed
- Monitor query time: check `EXPLAIN ANALYZE` for slow queries

### 2. Data Privacy
- Always use Stage 2B or Stage 3 for analysis (never Stage 1 raw data)
- Use hashed IDs to link records within Stage 2B
- Use aggregates in Stage 3 for public reporting
- Enable audit logging for all Stage 2B access

### 3. Data Quality
- Run Stage 1 validation after every extract
- Check transformation completeness in Stage 2A
- Verify pseudonymization in Stage 2B before releasing to researchers
- Monitor data quality trends over time

### 4. Maintenance
- Update stage_1 schema annually when SIS schema changes
- Re-generate views if transformation logic changes
- Archive old Stage 1 data per retention policy
- Rotate audit logs monthly

---

## Common Queries

### Find student GPA trend across terms
```sql
SELECT 
  er.term,
  AVG(er.gpa_contribution) as avg_gpa,
  COUNT(*) as enrollment_count
FROM stage_2b.enrollment_refined er
WHERE er.student_id_hashed = privacy.hash_pii('S12345')
GROUP BY er.term
ORDER BY er.term;
```

### Find courses with highest failure rate
```sql
SELECT 
  cr.course_id,
  cr.course_name,
  COUNT(*) as total_enrollments,
  COUNT(CASE WHEN er.letter_grade IN ('D', 'D-', 'F') THEN 1 END) as failing_count,
  ROUND(100.0 * COUNT(CASE WHEN er.letter_grade IN ('D', 'D-', 'F') THEN 1 END) / COUNT(*), 1) as failure_rate_percent
FROM stage_2b.enrollment_refined er
JOIN stage_2b.courses_refined cr ON er.course_id = cr.course_id
GROUP BY cr.course_id, cr.course_name
HAVING COUNT(CASE WHEN er.letter_grade IN ('D', 'D-', 'F') THEN 1 END) > 0
ORDER BY failure_rate_percent DESC
LIMIT 10;
```

### Find chronically absent students by grade level
```sql
SELECT 
  sr.grade_level,
  COUNT(DISTINCT sr.student_id_hashed) as chronic_absence_count,
  ROUND(AVG(sr.gpa), 2) as avg_gpa_of_chronic_absentees
FROM stage_2b.students_refined sr
JOIN stage_2b.attendance_refined ar ON sr.student_id_hashed = ar.student_id_hashed
WHERE ar.chronically_absent = true
GROUP BY sr.grade_level
ORDER BY sr.grade_level;
```

### Analyze special education program effectiveness
```sql
SELECT 
  'With Special Ed' as group_type,
  COUNT(DISTINCT sr.student_id_hashed) as student_count,
  ROUND(AVG(sr.gpa), 2) as avg_gpa,
  ROUND(AVG(ar.attendance_rate), 4) as avg_attendance,
  COUNT(CASE WHEN sr.special_education = true AND sr.special_education = true THEN 1 END) as actually_flagged
FROM stage_2b.students_refined sr
LEFT JOIN stage_2b.attendance_refined ar ON sr.student_id_hashed = ar.student_id_hashed
WHERE sr.special_education = true
UNION ALL
SELECT 
  'Without Special Ed',
  COUNT(DISTINCT sr.student_id_hashed),
  ROUND(AVG(sr.gpa), 2),
  ROUND(AVG(ar.attendance_rate), 4),
  0
FROM stage_2b.students_refined sr
LEFT JOIN stage_2b.attendance_refined ar ON sr.student_id_hashed = ar.student_id_hashed
WHERE sr.special_education = false;
```

---

## Troubleshooting

**Query Returns No Results**:
- Check if Stage 1 data was actually extracted
- Verify table names and schema: `\dt stage_2a.*`
- Check for NULLs in key fields: `SELECT COUNT(CASE WHEN student_id IS NULL THEN 1 END) FROM students;`

**Pseudonymization Hashes Don't Match**:
- Verify hash function exists: `\df privacy.hash_pii`
- Check that salt is set correctly in database settings
- Re-run pseudonymization if schema changed

**Performance Slow**:
- Run `ANALYZE` to update statistics: `ANALYZE stage_2b.students_refined;`
- Check indexes: `SELECT * FROM pg_indexes WHERE schemaname = 'stage_2b';`
- Use `EXPLAIN ANALYZE` to find bottleneck

**Audit Log Growing Too Large**:
- Archive old entries: `DELETE FROM stage_2b.privacy_audit_log WHERE accessed_timestamp < CURRENT_DATE - INTERVAL '90 days';`
- Set up automatic purging with a scheduled job

---

## References

- [PRIVACY_RULES.md](../docs/PRIVACY_RULES.md) - De-identification and pseudonymization strategy
- [DATA_DICTIONARY.md](../docs/DATA_DICTIONARY.md) - Field definitions and transformations
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - Overall system design and data flow
- [SCHEMAS.md](../SCHEMAS.md) - Stage-by-stage schema details

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Data Operations Team  
**Next Review**: When SIS schema changes or annually
