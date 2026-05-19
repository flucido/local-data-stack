# Privacy Rules and FERPA Compliance

## Overview

This document details the privacy and data protection rules implemented in the example SIS package. The framework is designed to comply with the **Family Educational Rights and Privacy Act (FERPA)** while enabling legitimate educational research and analytics.

### Key Principles

- **Pseudonymization** - Replace personally identifiable information (PII) with non-reversible tokens
- **Minimal Disclosure** - Restrict data access by role and use case
- **Consent-Based** - Honor student/parent opt-out preferences
- **Audit Trail** - Log all data access for compliance verification
- **Data Retention** - Enforce time-based and event-based purging

---

## FERPA Compliance Framework

### FERPA Overview

The Family Educational Rights and Privacy Act (20 U.S.C. § 1232g) protects student educational records by:

1. **Requiring parental/student consent** for disclosure (with exceptions)
2. **Allowing access by authorized parties** (school staff with legitimate educational interest)
3. **Permitting de-identified research data** with no re-identification risk
4. **Enforcing student rights** to view, correct, and challenge records

### De-Identification Under FERPA

FERPA defines de-identified education records as records where:

- **Direct identifiers are removed or encrypted**
  - Student name, ID, date of birth, Social Security number, email, phone
  - Parent/family member names
  - School or district name with specific student list

- **Indirect identifiers are eliminated or generalized**
  - Geographic location details that could re-identify (rare grade combinations + zip code = unique)
  - Dates that are linked to rare events
  - Coded student IDs that are traceable back to the original

- **No re-identification risk through external data linkage**
  - Cannot be matched to other datasets to recover identity
  - No key/codebook exists to reverse the de-identification

### Three-Stage Privacy Model

| Stage | Purpose | De-Identification | Access | Use Cases |
|-------|---------|-------------------|--------|-----------|
| **Stage 1: Raw** | Original data with audit trail | No | Authorized system operators only | Data quality checks, compliance audit |
| **Stage 2A: Normalized** | Standardized schema, no privacy transformation | Partial | Authorized data admins | Configuration verification, field mapping |
| **Stage 2B: Refined** | Pseudonymized, de-identified | Yes | Authorized researchers, educators | Analytics, dashboards, research |
| **Stage 3: Analytics** | Aggregated, no individual records | Yes | Public/dashboard | Summary statistics, trends |

---

## Pseudonymization Strategies

### Strategy 1: One-Way Hash (Deterministic Pseudonymization)

**Purpose**: Replace direct identifiers with deterministic tokens that are:
- Always the same for the same input (allows linking across datasets)
- Impossible to reverse (one-way encryption)
- Unique (low collision risk)

**Implementation**:
```
Hash Function: SHA-256 (256-bit cryptographic hash)
Salt: <16-byte random value> (stored securely, different per district)
Process: hash(field_value + salt) → 64-character hex string

Example:
  Input:  student_id = "S12345"
  Hash:   "a3c9f7e2b1d4c8a5f6e9b2c1d4e7f8a9b2c5d6e7f8a9b2c1d4e5f6a7b8c9"
  Output: "a3c9f7..."  (truncated for readability)
```

**Applied To**:
- `student_id` → `student_id_hashed`
- `teacher_id` → `teacher_id_hashed`
- `parent_id` → `parent_id_hashed`
- `date_of_birth` → `dob_hashed`
- `ssn` → `ssn_hashed`

**Characteristics**:
✓ Deterministic (same input always produces same output)
✓ Linkable (can connect records across tables/files)
✓ One-way (impossible to reverse even with the input value)
✓ FERPA-compliant (direct identifier removed)

**Limitations**:
✗ Input values can be brute-forced if dataset is small
✗ Linkage creates re-identification risk if combined with quasi-identifiers
✗ Hash collision risk with SHA-256 is negligible (~1 in 2^128)

---

### Strategy 2: Irreversible Mask (Non-Deterministic Pseudonymization)

**Purpose**: Replace sensitive text with masked/partially visible versions that:
- Are non-reversible (cannot recover original)
- Are non-deterministic (same input produces different output each time)
- Retain enough information for human recognition

**Implementation**:
```
Function: mask_text(value, visible_chars, mask_char='*')

first_name:
  Input:  "John"
  Output: "Jo**"  (show first 2 chars, mask rest)

last_name:
  Input:  "Smith"
  Output: "S****"  (show first 1 char, mask rest)

email:
  Input:  "john.smith@example.com"
  Output: "jo**@ex****.***"  (mask local and domain parts)

phone:
  Input:  "+1-555-123-4567"
  Output: "+1-555-****"  (show area code and exchange, mask local)

address:
  Input:  "123 Oak Street, Springfield, IL 62701"
  Output: "*** *** Street, Springfield, IL 62***"
```

**Applied To**:
- `first_name` → `first_name_masked`
- `last_name` → `last_name_masked`
- `email` → `email_masked`
- `phone` → `phone_masked`
- `address` → `address_masked`

**Characteristics**:
✓ Non-reversible (cannot recover original from masked value)
✓ Non-deterministic (each masking produces different result)
✓ Human-readable (enough info to verify record ownership)
✓ FERPA-compliant (direct identifier obscured)

**Limitations**:
✗ Non-deterministic (cannot reliably link across datasets)
✗ Mask patterns may leak information (all masked emails look similar)
✗ Partial visibility could enable re-identification with external data

---

### Strategy 3: No Operation (No Transformation)

**Purpose**: Leave non-sensitive fields unchanged because they:
- Contain no personally identifiable information (PII)
- Are essential for analytics and research
- Are already de-identified

**Applied To**:
- `grade_level` (1-12)
- `enrollment_status` (Active, Graduated, Withdrawn)
- `academic_program` (College Prep, Vocational, IEP)
- `attendance_rate` (0.0-1.0 percentage)
- `gpa` (0.0-4.0 scale)
- `grade` (A, B, C, D, F)
- `course_code` (ENG101, MATH201, etc.)
- `course_name` (English Composition, Algebra II, etc.)
- `credit_hours` (numeric)
- `term` (Fall 2024, Spring 2025)

**Characteristics**:
✓ No privacy impact (already de-identified)
✓ Full analytical value (preserves all information)
✓ Simple (no computation overhead)

---

## Field-Level Privacy Rules

### Students Entity

| Field | Type | Privacy Rule | Transformation | Stage 2B Example |
|-------|------|--------------|-----------------|-----------------|
| `student_id` | String | Hash | SHA-256 + salt | `a3c9f7e2...` |
| `first_name` | String | Mask | Show first 2, mask rest | `Jo****` |
| `last_name` | String | Mask | Show first 1, mask rest | `S****` |
| `date_of_birth` | Date | Hash | SHA-256 + salt | `b4d8e9f1...` |
| `grade_level` | Integer | No-op | No change | `10` |
| `enrollment_status` | String | No-op | No change | `Active` |
| `academic_program` | String | No-op | No change | `College Prep` |
| `email` | String | Mask | Show first 2 + domain, mask rest | `jo**@ex****.***` |
| `phone` | String | Mask | Show area code, mask local | `+1-555-****` |
| `address` | String | Mask | Show city/state, mask street/zip | `Springfield, IL` |
| `gender` | String | No-op | No change | `M` |
| `ethnicity` | String | No-op | No change | `Hispanic` |
| `special_education` | Boolean | No-op | No change | `true` |
| `english_learner` | Boolean | No-op | No change | `false` |
| `free_reduced_lunch` | Boolean | No-op | No change | `true` |
| `enrollment_date` | Date | No-op | No change | `2023-08-20` |
| `withdrawal_date` | Date | Null if withdrawn | Hide or blank | NULL |
| `prior_school` | String | No-op | No change | `Lincoln MS` |
| `iep_status` | String | No-op | No change | `IEP` |
| `disability_category` | String | No-op | No change | `Autism Spectrum` |
| `section_504_status` | String | No-op | No change | `504 Plan` |
| `gifted_status` | String | No-op | No change | `Identified` |
| `immigrant_status` | String | No-op | No change | `First-gen` |
| `homeless_status` | String | No-op | No change | `Housed` |
| `parent_first_name` | String | Mask | Show first 1, mask rest | `J****` |
| `parent_last_name` | String | Mask | Show first 1, mask rest | `S****` |
| `parent_email` | String | Mask | Show first 1 + domain, mask rest | `j**@ex****.***` |

---

### Courses Entity

| Field | Type | Privacy Rule | Transformation | Stage 2B Example |
|-------|------|--------------|-----------------|-----------------|
| `course_id` | String | No-op | No change | `ENG101` |
| `course_name` | String | No-op | No change | `English Composition` |
| `course_code` | String | No-op | No change | `ENG-101` |
| `grade_level_min` | Integer | No-op | No change | `9` |
| `grade_level_max` | Integer | No-op | No change | `12` |
| `subject` | String | No-op | No change | `English Language Arts` |
| `credit_hours` | Float | No-op | No change | `1.0` |
| `description` | String | No-op | No change | `Standard course...` |
| `term` | String | No-op | No change | `Fall 2024` |
| `meeting_schedule` | String | No-op | No change | `MWF 9:00-9:50 AM` |
| `instructor_first_name` | String | Mask | Show first 1, mask rest | `J****` |
| `instructor_last_name` | String | Mask | Show first 1, mask rest | `D****` |
| `instructor_id` | String | Hash | SHA-256 + salt | `c5e9f2d3...` |
| `instructor_email` | String | Mask | Show first 1 + domain | `j**@ex****.***` |
| `department` | String | No-op | No change | `English` |
| `capacity` | Integer | No-op | No change | `30` |
| `enrollment_count` | Integer | No-op | No change | `28` |
| `room_number` | String | No-op | No change | `201` |
| `prerequisites` | String | No-op | No change | `ENG100, WRIT101` |

---

### Enrollment Entity

| Field | Type | Privacy Rule | Transformation | Stage 2B Example |
|-------|------|--------------|-----------------|-----------------|
| `enrollment_id` | String | Hash | SHA-256 + salt | `d6f3a8e4...` |
| `student_id` | String | Hash | SHA-256 + salt | `a3c9f7e2...` |
| `course_id` | String | No-op | No change | `ENG101` |
| `grade` | String | No-op | No change | `A` |
| `gpa_contribution` | Float | No-op | No change | `4.0` |
| `term` | String | No-op | No change | `Fall 2024` |
| `final_grade_percent` | Float | No-op | No change | `92.5` |
| `completion_status` | String | No-op | No change | `Completed` |
| `credit_earned` | Float | No-op | No change | `1.0` |
| `enrollment_date` | Date | No-op | No change | `2024-08-20` |
| `withdrawal_date` | Date | Null if withdrawn | Hide if before term end | NULL |
| `advanced_placement` | Boolean | No-op | No change | `false` |
| `weighted_grade` | String | No-op | No change | `4.5` |
| `midterm_grade` | String | No-op | No change | `B+` |
| `finals_grade` | String | No-op | No change | `A-` |
| `assignment_completion_rate` | Float | No-op | No change | `0.95` |
| `quiz_average` | Float | No-op | No change | `88.5` |
| `test_average` | Float | No-op | No change | `91.2` |
| `participation_score` | Float | No-op | No change | `8.5` |
| `project_score` | Float | No-op | No change | `90.0` |
| `behavior_notes` | String | Mask | Show summary only, remove names | `Good participation...` |
| `accommodations` | String | No-op | No change | `Extended time` |
| `teacher_comment` | String | Mask | Remove student names | `Strong performance...` |
| `flag_for_intervention` | Boolean | No-op | No change | `false` |

---

### Attendance Entity

| Field | Type | Privacy Rule | Transformation | Stage 2B Example |
|-------|------|--------------|-----------------|-----------------|
| `attendance_id` | String | Hash | SHA-256 + salt | `e7a4b9c5...` |
| `student_id` | String | Hash | SHA-256 + salt | `a3c9f7e2...` |
| `date` | Date | Generalize to week/month | `2024-09-15` (week-level) | `2024-09-09` |
| `status` | String | No-op | No change | `Present` |
| `present_count` | Integer | No-op | No change | `4` |
| `absent_count` | Integer | No-op | No change | `1` |
| `tardy_count` | Integer | No-op | No change | `0` |
| `excused_count` | Integer | No-op | No change | `0` |
| `unexcused_count` | Integer | No-op | No change | `1` |
| `attendance_rate` | Float | No-op | No change | `0.98` |
| `cumulative_absence_rate` | Float | No-op | No change | `0.02` |
| `term` | String | No-op | No change | `Fall 2024` |
| `course_id` | String | No-op | No change | `ENG101` |
| `chronically_absent` | Boolean | No-op | No change | `false` |
| `warning_level` | String | No-op | No change | `None` |
| `trend` | String | No-op | No change | `Stable` |
| `attendance_pattern` | String | Generalize | Show pattern type only | `Weekend absence` |
| `reason_code` | String | No-op | No change | `Illness` |
| `reason_description` | String | Mask | Remove specific medical details | `Health-related absence` |
| `authorized_by` | String | Mask | Show first 1, mask rest | `J****` |
| `notes` | String | Remove PII | Hide names/addresses | `Absence notification sent` |

---

### Academic Records Entity

| Field | Type | Privacy Rule | Transformation | Stage 2B Example |
|-------|------|--------------|-----------------|-----------------|
| `record_id` | String | Hash | SHA-256 + salt | `f8b5c7a9...` |
| `student_id` | String | Hash | SHA-256 + salt | `a3c9f7e2...` |
| `course_id` | String | No-op | No change | `MATH201` |
| `assignment_name` | String | No-op | No change | `Chapter 3 Quiz` |
| `assignment_date` | Date | No-op | No change | `2024-09-15` |
| `assignment_type` | String | No-op | No change | `Quiz` |
| `max_points` | Float | No-op | No change | `100.0` |
| `earned_points` | Float | No-op | No change | `92.5` |
| `score_percent` | Float | No-op | No change | `92.5` |
| `mastery_level` | String | No-op | No change | `Proficient` |
| `submission_date` | Date | No-op | No change | `2024-09-15` |
| `submission_method` | String | No-op | No change | `Online` |
| `on_time` | Boolean | No-op | No change | `true` |
| `late_days` | Integer | No-op | No change | `0` |
| `retake_count` | Integer | No-op | No change | `1` |
| `original_score` | Float | No-op | No change | `85.0` |
| `feedback_provided` | Boolean | No-op | No change | `true` |
| `competency_id` | String | No-op | No change | `MATH-2.1` |
| `competency_name` | String | No-op | No change | `Quadratic Equations` |
| `standard_code` | String | No-op | No change | `CC.9-12.A.REI.4` |
| `evidence_of_learning` | String | Mask | Summarize without examples | `Demonstrates proficiency` |
| `teacher_feedback` | String | Mask | Remove personal comments | `Work shows solid understanding` |
| `remediation_offered` | Boolean | No-op | No change | `false` |
| `enrichment_offered` | Boolean | No-op | No change | `true` |

---

## Privacy Transformation Examples

### Example 1: Student Record Transformation

**Stage 1 (Raw):**
```
student_id: S123456
first_name: John
last_name: Smith
date_of_birth: 2008-05-15
email: john.smith@example.com
phone: +1-555-123-4567
address: 123 Oak Street, Springfield, IL 62701
grade_level: 10
gpa: 3.85
```

**Stage 2B (Privacy-Compliant):**
```
student_id: a3c9f7e2b1d4c8a5f6e9b2c1d4e7f8a9
first_name: Jo****
last_name: S****
date_of_birth: b4d8e9f1c5a2d9e6b1f4c7a0d3e6f2a9
email: jo**@ex****.***
phone: +1-555-****
address: Springfield, IL
grade_level: 10
gpa: 3.85
```

---

### Example 2: Course Enrollment with Grades

**Stage 1 (Raw):**
```
enrollment_id: E456789
student_id: S123456
course_id: ENG101
instructor_name: Jane Doe
grade: A-
final_grade_percent: 92.5
```

**Stage 2B (Privacy-Compliant):**
```
enrollment_id: d6f3a8e4a2c1b9e7f6d4c3b1a9f8e7d6
student_id: a3c9f7e2b1d4c8a5f6e9b2c1d4e7f8a9
course_id: ENG101
instructor_name: J****
grade: A-
final_grade_percent: 92.5
```

---

### Example 3: Attendance Record Transformation

**Stage 1 (Raw):**
```
attendance_id: AT789012
student_id: S123456
date: 2024-09-15
status: Absent
reason: Doctor's appointment at Springfield Medical
authorized_by: Dr. Johnson
attendance_rate: 0.98
```

**Stage 2B (Privacy-Compliant):**
```
attendance_id: e7a4b9c5d2e8f1a4b7c0d3e6f9a2b5c8
student_id: a3c9f7e2b1d4c8a5f6e9b2c1d4e7f8a9
date: 2024-09-09  (generalized to week)
status: Absent
reason: Health-related absence
authorized_by: D****
attendance_rate: 0.98
```

---

## Access Control by Role

### Role-Based Data Access Matrix

| Role | Stage 1 | Stage 2A | Stage 2B | Stage 3 | Purpose |
|------|---------|---------|---------|---------|---------|
| **SIS Operator** | ✓ Full | ✓ Full | ✗ None | ✗ None | Data extraction, system maintenance |
| **Data Admin** | ✓ Full | ✓ Full | ✓ Assigned districts | ✓ Assigned districts | Configuration, data quality monitoring |
| **Building Principal** | ✗ None | ✗ None | ✓ Own building | ✓ Own building | School-level dashboards, student support |
| **Teacher** | ✗ None | ✗ None | ✓ Own students | ✓ Own students | Classroom analytics, student progress |
| **Counselor** | ✗ None | ✗ None | ✓ Assigned students | ✓ Assigned students | Student support, intervention tracking |
| **Researcher (Approved)** | ✗ None | ✗ None | ✓ District-level aggregates | ✓ Public aggregates | Research projects, program evaluation |
| **Dashboard User** | ✗ None | ✗ None | ✗ None | ✓ Aggregates | Public dashboards, district trends |

### Detailed Access Rules

**Stage 1: Raw (Authorized Operators Only)**
- SIS administrators and system operators
- Reason: Original data with all PII intact
- Restrictions: Single-user sessions, all access logged
- Audit: Every access recorded with timestamp, query, and data volume

**Stage 2A: Normalized (Data Admins)**
- Data administrators and configuration managers
- Reason: Verify field mappings, validate transformations
- Restrictions: Read-only access to test records only during configuration
- Audit: Configuration changes tracked with version control

**Stage 2B: Refined (Role-Based, Privacy-Compliant)**
- Building principals: Own building data only
- Teachers: Own students and courses only
- Counselors: Assigned students only
- Researchers: District-level aggregates only
- Reason: Pseudonymized data suitable for analysis
- Restrictions: Row-level security (RLS) enforced at database level
- Audit: All queries logged, data exports tracked

**Stage 3: Analytics (Public Aggregates)**
- Dashboard viewers: Aggregated statistics only
- No individual student records
- Grade level, school, district level only
- Reason: Fully de-identified, no re-identification risk

---

## Consent and Data Lifecycle Management

### Student/Parent Consent

**Opt-Out Scenarios:**

1. **Research Opt-Out**
   - Student/parent requests data not used for research beyond school operations
   - Action: Flag in `research_opt_out` field
   - Impact: Record excluded from Stage 3 analytics, researcher datasets
   - Kept in Stages 1-2B for operational purposes

2. **Analytics Opt-Out**
   - Student/parent requests data not displayed in dashboards
   - Action: Flag in `dashboard_opt_out` field
   - Impact: Record excluded from Stage 3 dashboards, but included in Stage 2B research
   - Kept in Stages 1-2B for operational purposes

3. **Full Opt-Out**
   - Student/parent requests complete data removal
   - Action: Flag in `do_not_collect` field
   - Impact: Record purged from Stages 2B-3 immediately
   - Kept in Stage 1 for 7 years (legal compliance), Stage 2A for 5 years (operational audit)

4. **Deceased Student**
   - Student is deceased
   - Action: Flag in `deceased` field with date
   - Impact: Record purged from all stages after 7-year retention period
   - Immediate removal from dashboards, research datasets

### Data Retention Policies

| Data Stage | Retention Period | Purge Trigger | Legal Basis |
|------------|------------------|---------------|-------------|
| **Stage 1: Raw** | 7 years | Student graduation + 7 years | FERPA, Tax law |
| **Stage 2A: Normalized** | 5 years | Configuration expiry | Audit trail |
| **Stage 2B: Refined** | 3 years | Current term + 3 years | School policy |
| **Stage 3: Analytics** | Indefinite | None | Aggregated only |
| **Opt-Out Records** | Immediate | Consent revocation | FERPA right to refuse |

**Automated Purging:**
```sql
-- Nightly job to identify purge candidates
SELECT student_id, stage, created_date
FROM audit_log
WHERE (graduation_date + INTERVAL '7 years') < NOW()
  OR (consent_opt_out = true AND opt_out_date < NOW() - INTERVAL '30 days')
  OR (is_deceased = true AND death_date < NOW() - INTERVAL '7 years')
```

---

## Incident Response Procedures

### Privacy Incident Classification

**Level 1: Minor (No student impact)**
- Unauthorized access attempt blocked by RLS
- Query logs show no data retrieved
- Action: Log, monitor for patterns

**Level 2: Moderate (Limited exposure)**
- 1-10 records exposed to unauthorized user
- <5 minutes before access revoked
- Action: Log, notify user, audit affected records

**Level 3: Major (Significant exposure)**
- 11-100 records exposed to unauthorized user
- >5 minutes before access revoked
- Action: Log, notify supervisor, trigger incident response

**Level 4: Critical (Mass exposure)**
- >100 records exposed, or full dataset exposed
- Extended unauthorized access period
- Action: Immediate shutdown, law enforcement notification, parent notification

### Response Workflow

**Within 1 hour:**
- Identify scope: How many records? Which fields? Which students?
- Disable affected user account
- Review access logs (Stage 1 & 2B query history)
- Document exposure: Who accessed? When? What data?

**Within 24 hours:**
- Notify security team and data protection officer
- Determine if FERPA violation occurred
- Assess parent/student notification requirements (varies by state)
- Begin audit of all access logs

**Within 7 days:**
- Complete incident investigation
- Implement preventive controls
- Document lessons learned
- Notify affected parties if required

**Follow-up:**
- Monthly: Review incidents, identify trends
- Quarterly: Access control audit
- Annually: Privacy training for all data handlers

---

## Pseudonymization Challenges and Limitations

### Re-Identification Risk Assessment

**Scenario 1: Quasi-Identifier Linkage**
```
Public dataset:  [Grade 10, Female, Springfield, IL 62701]
De-identified data: [Grade 10, Female, attendance_rate=98%, gpa=3.9]

Risk: If unique combination exists, student could be identified
Mitigation: Generalize geographic location (remove zip code)
```

**Scenario 2: External Data Matching**
```
Public dataset: [High school name, Grade 10, Female, Graduation year 2025]
De-identified data: [grade_level=10, gender=Female, courses=AP Biology, AP English]

Risk: Combined knowledge could identify student
Mitigation: Aggregate by school or grade level, never publish course lists
```

**Scenario 3: Temporal Attacks**
```
Before pseudonymization: Student John Smith, DOB 2008-05-15
After pseudonymization: hash_dob = "b4d8e9f1..."

Risk: Hash value is stable over time and linkable across datasets
Mitigation: Use unique salt per district, re-hash with new salt annually
```

### Best Practices

✓ **DO**:
- Use cryptographically secure hashing (SHA-256 or stronger)
- Store salts separately from hashed values
- Re-salt and re-hash annually with new random salt
- Generalize quasi-identifiers (age, location, demographics)
- Aggregate to school/grade level, never individual
- Conduct privacy impact assessments for research projects
- Implement row-level security at database level
- Log all data access and monitor for anomalies
- Train staff on privacy and data protection

✗ **DON'T**:
- Use weak hashing algorithms (MD5, SHA-1)
- Re-use same salt across districts or time periods
- Publish raw de-identified datasets without analysis
- Combine de-identified data with public information sources
- Allow researchers to contact students via de-identified IDs
- Store de-identification keys in the same database as hashed data
- Skip security patches or let credentials expire
- Download production data to personal devices
- Share Stage 2B data outside district without formal agreement

---

## Implementation Checklist

### Before Going Live

- [ ] Privacy audit completed and documented
- [ ] Role-based access control (RBAC) configured in database
- [ ] Row-level security (RLS) policies enabled
- [ ] Hashing salt generated and stored securely (separate system)
- [ ] Audit logging enabled for all stages
- [ ] Data retention policies configured in scheduler
- [ ] Opt-out fields added to student record system
- [ ] Staff trained on privacy procedures
- [ ] Legal review of data use agreements completed
- [ ] Incident response procedures documented and tested
- [ ] Monitoring alerts configured for unauthorized access attempts

### Ongoing Compliance

- [ ] Monthly: Review access logs for anomalies
- [ ] Quarterly: Audit user role assignments
- [ ] Semi-annually: Privacy training for staff
- [ ] Annually: Re-hash all pseudonymized values with new salt
- [ ] Annually: Privacy impact assessment update

---

## References

- [FERPA Overview](https://www2.ed.gov/policy/gen/guid/fpco/ferpa/)
- [FERPA De-Identification Guidance](https://www2.ed.gov/policy/gen/guid/fpco/ferpa/lea-officials.html)
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework)
- [State Education Agency FERPA Standards](https://www.ets.org/s/about/pdf/ferpa_overview.pdf)

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Data Governance Team  
**Next Review**: Annually or upon policy changes
