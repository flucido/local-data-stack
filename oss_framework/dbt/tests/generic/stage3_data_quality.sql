-- Stage 3 Analytics Marts - Comprehensive Data Quality Tests
-- These tests ensure analytics views meet production standards

-- Test 1: No null values in critical key columns
SELECT *
FROM {{ ref('v_chronic_absenteeism_risk') }}
WHERE student_key IS NULL
  OR school_id IS NULL
  OR chronic_absenteeism_risk_score IS NULL
LIMIT 1;

-- Test 2: Risk scores are within valid range (0-100)
SELECT *
FROM {{ ref('v_chronic_absenteeism_risk') }}
WHERE chronic_absenteeism_risk_score < 0
  OR chronic_absenteeism_risk_score > 100
LIMIT 1;

-- Test 3: Risk classifications match score ranges
SELECT *
FROM {{ ref('v_chronic_absenteeism_risk') }}
WHERE (chronic_absenteeism_risk_score > 70 AND risk_classification != 'Critical')
  OR (chronic_absenteeism_risk_score BETWEEN 40 AND 70 AND risk_classification != 'High')
  OR (chronic_absenteeism_risk_score BETWEEN 10 AND 40 AND risk_classification != 'Medium')
  OR (chronic_absenteeism_risk_score < 10 AND risk_classification != 'Low')
LIMIT 1;

-- Test 4: Attendance rates are valid percentages (0-100)
SELECT *
FROM {{ ref('v_chronic_absenteeism_risk') }}
WHERE attendance_rate_30d < 0
  OR attendance_rate_30d > 100
  OR attendance_rate_90d < 0
  OR attendance_rate_90d > 100
LIMIT 1;

-- Test 5: No duplicate student records in wellbeing view
SELECT student_key, COUNT(*) as cnt
FROM {{ ref('v_wellbeing_risk_profiles') }}
GROUP BY student_key
HAVING COUNT(*) > 1
LIMIT 1;

-- Test 6: Equity outcomes view - min 5 students per demographic cell
SELECT demographic_group, COUNT(DISTINCT student_key) as student_count
FROM {{ ref('v_equity_outcomes_by_demographics') }}
GROUP BY demographic_group
HAVING COUNT(DISTINCT student_key) < 5
LIMIT 1;

-- Test 7: Performance correlations view - valid correlation coefficients
SELECT *
FROM {{ ref('v_performance_correlations') }}
WHERE correlation_strength < -1
  OR correlation_strength > 1
LIMIT 1;

-- Test 8: Class section comparison - valid percentiles
SELECT *
FROM {{ ref('v_class_section_comparison') }}
WHERE percentile_rank < 0
  OR percentile_rank > 100
LIMIT 1;

-- Test 9: Referential integrity - all students in analytics views exist in dimension
SELECT v.student_key
FROM {{ ref('v_chronic_absenteeism_risk') }} v
LEFT JOIN {{ ref('dim_students') }} d ON v.student_key = d.student_id_hash
WHERE d.student_id_hash IS NULL
LIMIT 1;

-- Test 10: Data freshness - views have recent data (within last 7 days)
SELECT 
  COUNT(*) as total_records,
  MAX(CAST(created_at AS DATE)) as max_date
FROM {{ ref('v_chronic_absenteeism_risk') }}
WHERE CAST(created_at AS DATE) < CURRENT_DATE - INTERVAL '7 days'
LIMIT 1;
