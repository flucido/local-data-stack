# Testing Strategy & Implementation

## Overview

Comprehensive test suite for the oss_framework library covering unit tests, integration tests, and education-specific validation. Target: **80%+ code coverage** with pytest.

## Test Organization

```
oss_framework/tests/
├── conftest.py                      Shared fixtures for all tests
├── test_data_transformations.py     Unit tests: data handling, transformations
├── test_batch_processing.py         Integration tests: batch modes, quality checks
└── test_education_validation.py     Education-specific: metrics, outcomes, equity
```

## Test Coverage by Module

### 1. Data Transformations (`test_data_transformations.py`)

**Unit Tests**: 15 tests covering core data operations

#### TestDataTransformer (8 tests)
- `test_flatten_json_simple`: JSON flattening with nested structures
- `test_normalize_numeric_columns`: Min-max scaling on numeric data
- `test_handle_missing_values_drop`: Drop rows with NaN
- `test_handle_missing_values_forward_fill`: Forward fill missing values
- `test_validate_data_types`: Type validation against schema

#### TestEngagementAggregator (3 tests)
- `test_calculate_engagement_score`: Aggregate engagement metrics
- `test_aggregate_engagement_by_course`: Group engagement by course
- `test_calculate_attendance_metrics`: Calculate attendance rates

#### TestPseudonymizer (4 tests)
- `test_hash_student_id`: Deterministic hashing of IDs
- `test_mask_names`: One-way masking of PII
- `test_no_op_grades`: Retain non-sensitive data unchanged
- `test_hash_consistency`: Same input produces same hash

#### TestSchemaValidator (3 tests)
- `test_validate_required_columns`: Check mandatory fields present
- `test_validate_data_types`: Verify column types match schema
- `test_validate_with_nulls`: Handle null values in validation

### 2. Batch Processing (`test_batch_processing.py`)

**Integration Tests**: 12 tests covering complete workflows

#### TestBatchProcessing (5 tests)
- `test_delta_batch_mode`: Incremental updates (merge on key)
- `test_additive_batch_mode`: Append-only mode
- `test_snapshot_batch_mode`: Full replacement
- `test_deduplication`: Remove duplicate records
- `test_error_handling_missing_key`: Error on invalid config

#### TestDataQualityChecks (4 tests)
- `test_null_check`: Detect missing values
- `test_duplicate_detection`: Identify duplicate records
- `test_outlier_detection`: Find statistical anomalies
- `test_type_consistency_check`: Validate type consistency

#### TestEndToEndPipeline (3 tests)
- `test_students_pipeline`: Complete student data flow
- `test_enrollment_pipeline`: Complete enrollment flow
- `test_multi_entity_join`: Multi-table joins and aggregation

### 3. Education Validation (`test_education_validation.py`)

**Domain Tests**: 18 tests for education-specific logic

#### TestEducationMetrics (5 tests)
- `test_gpa_calculation`: Weighted GPA computation (4.0 scale)
- `test_attendance_rate_calculation`: Attendance percentage
- `test_chronic_absenteeism_flag`: Identify chronic absences (<90%)
- `test_academic_risk_flag`: Multi-factor risk identification
- `test_engagement_categories`: Categorize engagement levels

#### TestStudentOutcomesPrediction (3 tests)
- `test_completion_likelihood_model`: Course completion predictors
- `test_grade_prediction_factors`: Factors predicting final grades
- `test_dropout_risk_factors`: Early warning indicators

#### TestDataIntegrity (4 tests)
- `test_enrollment_consistency`: Validate enrollment-student linking
- `test_grade_scale_validity`: Grades within 0-100 range
- `test_credit_accumulation`: Correct credit calculations
- `test_temporal_consistency`: Dates in correct order

#### TestCohortAnalysis (4 tests)
- `test_cohort_graduation_rate`: Graduation rates by cohort
- `test_subgroup_achievement_gap`: Achievement gaps across groups
- `test_equity_indicators`: Equity measure calculations

## Test Fixtures

All tests use standardized fixtures from `conftest.py`:

### Data Fixtures
- `sample_students_df`: 5 students with demographics
- `sample_courses_df`: 4 courses across 2 schools
- `sample_enrollment_df`: 6 enrollments with grades/attendance
- `sample_engagement_df`: 5 LMS engagement events
- `sample_attendance_df`: 5 daily attendance records
- `sample_academic_records_df`: 5 assignment grades

### Component Fixtures
- `metadata_manager`: MetadataManager loaded with combined schema
- `data_transformer`: DataTransformer with metadata
- `batch_processor`: BatchProcessor with metadata
- `pseudonymizer`: Pseudonymizer with metadata

### Utility Fixtures
- `temp_dir`: Temporary directory for file I/O tests

## Running the Tests

### Run all tests with coverage
```bash
cd /path/to/local-data-stack/oss_framework
pytest --cov=oss_framework --cov-report=html
```

### Run specific test categories
```bash
pytest -m unit               # Unit tests only
pytest -m integration        # Integration tests only
pytest -m education          # Education-specific tests
pytest -v                    # Verbose output
pytest -k "test_gpa"        # Run specific test by name
```

### Run with detailed reporting
```bash
pytest --tb=short --strict-markers -v --cov-report=term-missing
```

## Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| data_transformations.py | 80%+ | [Run tests] |
| batch_processing.py | 80%+ | [Run tests] |
| metadata_management.py | 80%+ | [Run tests] |
| Overall | 80%+ | [Run tests] |

## Test Data Strategy

Tests use realistic education data:

- **Students**: K-12 grade levels, special populations (ELL, SPED, disadvantaged)
- **Courses**: Multiple subjects (ELA, Math, Science, History) across schools
- **Enrollment**: Mix of passing/failing grades, varying attendance
- **Engagement**: LMS activity (page views, submissions, quizzes, discussions)
- **Attendance**: Present/absent, tardy, excused/unexcused absences
- **Academic Records**: Assignment types (homework, quiz, exam, project)

## Continuous Integration

For CI/CD pipelines:

```bash
pytest \
  --cov=oss_framework \
  --cov-fail-under=80 \
  --cov-report=xml \
  --junit-xml=test-results.xml \
  --tb=short
```

Exit code indicates:
- `0`: All tests passed, coverage ≥ 80%
- `1`: Tests failed or coverage < 80%

## Test Maintenance

### Adding New Tests
1. Choose appropriate test file based on module
2. Use existing fixtures from `conftest.py`
3. Mark test with appropriate marker: `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.education`
4. Keep test functions focused on single scenario
5. Use descriptive docstrings for test purpose

### Updating Fixtures
1. Add to `conftest.py` if reused by multiple tests
2. Document fixture purpose and data structure
3. Keep sample data realistic and representative

## Dependencies

Test requirements in `requirements.txt`:
```
pytest>=7.0
pytest-cov>=4.0
pandas>=1.5.0
numpy>=1.23.0
pyyaml>=6.0
```

## Related Documentation

- **Framework Architecture**: `../docs/tech_docs/data_lake_architecture.md`
- **Metadata System**: `../metadata/README.md`
- **Utilities API**: `../utilities/oss_framework/__init__.py`
