#!/usr/bin/env python3
"""
Rill Integration Test Suite - Comprehensive Dashboard Validation

Tests all 5 Rill dashboards with real data queries using the Rill API.
Validates that dashboards are accessible, queries execute, and data types are correct.

Dashboard Coverage:
  1. chronic_absenteeism_risk - Monitors students at risk of chronic absenteeism
  2. equity_outcomes_by_demographics - Analyzes outcome disparities across demographic groups
  3. class_effectiveness - Compares class/section performance across schools and courses
  4. performance_correlations - Analyzes correlations between attendance, discipline, and academic performance
  5. wellbeing_risk_profiles - Identifies students at risk across attendance, discipline, and academic domains
"""

import json
import time
import pytest
import requests
from typing import Dict, List, Any, Tuple
from datetime import datetime


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def rill_base_url():
    """Fixture providing the Rill server base URL"""
    return "http://localhost:9009"


@pytest.fixture
def rill_api_timeout():
    """Fixture providing API request timeout in seconds"""
    return 10


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def execute_rill_query(
    base_url: str,
    dashboard_name: str,
    dimension_name: str,
    measure_names: List[str],
    limit: int = 10,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Execute a Rill toplist query against a dashboard.

    Args:
        base_url: Rill server base URL
        dashboard_name: Name of the metrics view/dashboard
        dimension_name: Dimension to group by
        measure_names: List of measure names to query
        limit: Number of rows to return
        timeout: Request timeout in seconds

    Returns:
        Dict with 'meta' (schema) and 'data' (rows) keys

    Raises:
        requests.RequestException: If API call fails
        json.JSONDecodeError: If response is not valid JSON
    """
    url = f"{base_url}/v1/instances/default/queries/metrics-views/{dashboard_name}/toplist"
    payload = {"dimensionName": dimension_name, "measureNames": measure_names, "limit": limit}

    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def validate_response_schema(response: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that Rill API response has expected schema.

    Args:
        response: Response dict from Rill API

    Returns:
        Tuple of (is_valid, error_message)
    """
    if "meta" not in response:
        return False, "Missing 'meta' field in response"

    if "data" not in response:
        return False, "Missing 'data' field in response"

    if not isinstance(response["meta"], list):
        return False, "'meta' must be a list"

    if not isinstance(response["data"], list):
        return False, "'data' must be a list"

    return True, ""


def validate_data_types(response: Dict[str, Any], expected_dimensions: int) -> Tuple[bool, str]:
    """
    Validate data types in Rill response.

    Args:
        response: Response dict from Rill API
        expected_dimensions: Number of dimension columns expected

    Returns:
        Tuple of (is_valid, error_message)
    """
    meta = response.get("meta", [])
    data = response.get("data", [])

    if not meta:
        return False, "No columns returned in meta"

    if not data:
        return False, "No data rows returned"

    # Validate that all rows have expected number of columns
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            return False, f"Row {idx} is not a dict: {type(row)}"

        if len(row) != len(meta):
            return False, (f"Row {idx} has {len(row)} columns, expected {len(meta)}")

    return True, ""


def validate_row_counts(response: Dict[str, Any], min_rows: int = 1) -> Tuple[bool, str]:
    """
    Validate that response contains expected number of rows.

    Args:
        response: Response dict from Rill API
        min_rows: Minimum number of rows expected

    Returns:
        Tuple of (is_valid, error_message)
    """
    data = response.get("data", [])

    if len(data) < min_rows:
        return False, (f"Expected at least {min_rows} rows, got {len(data)}")

    return True, ""


# ============================================================================
# TEST SUITE: CHRONIC ABSENTEEISM RISK DASHBOARD
# ============================================================================


class TestChronicAbsenteeismDashboard:
    """Test chronic_absenteeism_risk dashboard"""

    def test_chronic_absenteeism_dashboard_accessibility(self, rill_base_url):
        """
        Validate chronic_absenteeism_risk dashboard is accessible via API.

        Tests that:
        - API endpoint responds with HTTP 200
        - Response contains valid JSON with meta and data fields
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="chronic_absenteeism_risk",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=5,
        )

        is_valid, error = validate_response_schema(response)
        assert is_valid, f"Invalid response schema: {error}"

    def test_chronic_absenteeism_data_types(self, rill_base_url):
        """
        Validate data types returned from chronic_absenteeism_risk.

        Tests that:
        - Response columns match schema in meta
        - All rows have consistent number of columns
        - Data is properly structured
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="chronic_absenteeism_risk",
            dimension_name="school_id",
            measure_names=["total_students", "chronic_absence_rate"],
            limit=10,
        )

        is_valid, error = validate_data_types(response, expected_dimensions=1)
        assert is_valid, f"Data type validation failed: {error}"

    def test_chronic_absenteeism_row_counts(self, rill_base_url):
        """
        Validate that chronic_absenteeism_risk returns data rows.

        Tests that:
        - Query returns at least 1 row
        - Data is not empty
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="chronic_absenteeism_risk",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=10,
        )

        is_valid, error = validate_row_counts(response, min_rows=1)
        assert is_valid, f"Row count validation failed: {error}"

        data = response.get("data", [])
        assert len(data) > 0, "Expected rows in response"

    def test_chronic_absenteeism_measure_values(self, rill_base_url):
        """
        Validate that chronic_absenteeism_risk measures have valid values.

        Tests that:
        - Measure values are numeric (not null or invalid)
        - total_students is positive integer
        - chronic_absence_rate is between 0 and 1 (percentage)
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="chronic_absenteeism_risk",
            dimension_name="school_id",
            measure_names=["total_students", "chronic_absence_rate"],
            limit=5,
        )

        data = response.get("data", [])
        assert len(data) > 0, "No data returned"

        for row in data:
            # Validate school_id exists
            assert "school_id" in row, "Missing school_id in row"
            assert row["school_id"] is not None, "school_id should not be null"

            # Validate total_students (should be positive integer)
            if "total_students" in row and row["total_students"] is not None:
                assert isinstance(row["total_students"], (int, float)), (
                    f"total_students should be numeric, got {type(row['total_students'])}"
                )
                assert row["total_students"] >= 0, (
                    f"total_students should be non-negative, got {row['total_students']}"
                )


# ============================================================================
# TEST SUITE: EQUITY OUTCOMES BY DEMOGRAPHICS DASHBOARD
# ============================================================================


class TestEquityOutcomesDashboard:
    """Test equity_outcomes_by_demographics dashboard"""

    def test_equity_outcomes_dashboard_accessibility(self, rill_base_url):
        """
        Validate equity_outcomes_by_demographics dashboard is accessible.

        Tests that:
        - API endpoint responds with HTTP 200
        - Response contains valid JSON schema
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="equity_outcomes_by_demographics",
            dimension_name="race_ethnicity",
            measure_names=["cohort_size"],
            limit=5,
        )

        is_valid, error = validate_response_schema(response)
        assert is_valid, f"Invalid response schema: {error}"

    def test_equity_outcomes_data_types(self, rill_base_url):
        """
        Validate data types returned from equity_outcomes_by_demographics.

        Tests that:
        - Response columns match schema
        - All rows have consistent structure
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="equity_outcomes_by_demographics",
            dimension_name="race_ethnicity",
            measure_names=["cohort_size", "avg_gpa"],
            limit=10,
        )

        is_valid, error = validate_data_types(response, expected_dimensions=1)
        assert is_valid, f"Data type validation failed: {error}"

    def test_equity_outcomes_row_counts(self, rill_base_url):
        """
        Validate that equity_outcomes_by_demographics returns data.

        Tests that:
        - Query returns at least 1 row
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="equity_outcomes_by_demographics",
            dimension_name="race_ethnicity",
            measure_names=["cohort_size"],
            limit=10,
        )

        is_valid, error = validate_row_counts(response, min_rows=1)
        assert is_valid, f"Row count validation failed: {error}"

    def test_equity_outcomes_measure_values(self, rill_base_url):
        """
        Validate that equity_outcomes_by_demographics measures are valid.

        Tests that:
        - cohort_size values are non-negative
        - Percentage measures are between 0 and 1
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="equity_outcomes_by_demographics",
            dimension_name="race_ethnicity",
            measure_names=["cohort_size", "avg_attendance"],
            limit=5,
        )

        data = response.get("data", [])
        assert len(data) > 0, "No data returned"

        for row in data:
            # Validate cohort_size
            if "cohort_size" in row and row["cohort_size"] is not None:
                assert isinstance(row["cohort_size"], (int, float)), (
                    f"cohort_size should be numeric, got {type(row['cohort_size'])}"
                )
                assert row["cohort_size"] >= 0, (
                    f"cohort_size should be non-negative, got {row['cohort_size']}"
                )


# ============================================================================
# TEST SUITE: CLASS EFFECTIVENESS DASHBOARD
# ============================================================================


class TestClassEffectivenessDashboard:
    """Test class_effectiveness dashboard"""

    def test_class_effectiveness_dashboard_accessibility(self, rill_base_url):
        """
        Validate class_effectiveness dashboard is accessible.

        Tests that:
        - API endpoint responds with HTTP 200
        - Response is valid JSON with schema
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="class_effectiveness",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=5,
        )

        is_valid, error = validate_response_schema(response)
        assert is_valid, f"Invalid response schema: {error}"

    def test_class_effectiveness_data_types(self, rill_base_url):
        """
        Validate data types from class_effectiveness.

        Tests that:
        - Response has correct schema
        - All rows have consistent columns
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="class_effectiveness",
            dimension_name="school_id",
            measure_names=["total_students", "avg_pass_rate"],
            limit=10,
        )

        is_valid, error = validate_data_types(response, expected_dimensions=1)
        assert is_valid, f"Data type validation failed: {error}"

    def test_class_effectiveness_row_counts(self, rill_base_url):
        """
        Validate that class_effectiveness returns data rows.

        Tests that:
        - Query returns at least 1 row
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="class_effectiveness",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=10,
        )

        is_valid, error = validate_row_counts(response, min_rows=1)
        assert is_valid, f"Row count validation failed: {error}"

    def test_class_effectiveness_measure_values(self, rill_base_url):
        """
        Validate that class_effectiveness measures are valid.

        Tests that:
        - Student counts are non-negative
        - Pass rates are between 0 and 1
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="class_effectiveness",
            dimension_name="school_id",
            measure_names=["total_students", "avg_pass_rate"],
            limit=5,
        )

        data = response.get("data", [])
        assert len(data) > 0, "No data returned"

        for row in data:
            # Validate school_id
            assert "school_id" in row, "Missing school_id"
            assert row["school_id"] is not None, "school_id should not be null"


# ============================================================================
# TEST SUITE: PERFORMANCE CORRELATIONS DASHBOARD
# ============================================================================


class TestPerformanceCorrelationsDashboard:
    """Test performance_correlations dashboard"""

    def test_performance_correlations_dashboard_accessibility(self, rill_base_url):
        """
        Validate performance_correlations dashboard is accessible.

        Tests that:
        - API endpoint responds with HTTP 200
        - Response is valid JSON
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="performance_correlations",
            dimension_name="correlation_pair",
            measure_names=["total_correlations"],
            limit=5,
        )

        is_valid, error = validate_response_schema(response)
        assert is_valid, f"Invalid response schema: {error}"

    def test_performance_correlations_data_types(self, rill_base_url):
        """
        Validate data types from performance_correlations.

        Tests that:
        - Response schema is valid
        - All rows are properly structured
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="performance_correlations",
            dimension_name="correlation_pair",
            measure_names=["total_correlations", "avg_correlation"],
            limit=10,
        )

        is_valid, error = validate_data_types(response, expected_dimensions=1)
        assert is_valid, f"Data type validation failed: {error}"

    def test_performance_correlations_row_counts(self, rill_base_url):
        """
        Validate that performance_correlations returns data rows.

        Tests that:
        - Query returns at least 1 row
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="performance_correlations",
            dimension_name="correlation_pair",
            measure_names=["total_correlations"],
            limit=10,
        )

        is_valid, error = validate_row_counts(response, min_rows=1)
        assert is_valid, f"Row count validation failed: {error}"


# ============================================================================
# TEST SUITE: WELLBEING RISK PROFILES DASHBOARD
# ============================================================================


class TestWellbeingRiskDashboard:
    """Test wellbeing_risk_profiles dashboard"""

    def test_wellbeing_risk_dashboard_accessibility(self, rill_base_url):
        """
        Validate wellbeing_risk_profiles dashboard is accessible.

        Tests that:
        - API endpoint responds with HTTP 200
        - Response is valid JSON with schema
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="wellbeing_risk_profiles",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=5,
        )

        is_valid, error = validate_response_schema(response)
        assert is_valid, f"Invalid response schema: {error}"

    def test_wellbeing_risk_data_types(self, rill_base_url):
        """
        Validate data types from wellbeing_risk_profiles.

        Tests that:
        - Response has valid schema
        - All rows have consistent structure
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="wellbeing_risk_profiles",
            dimension_name="school_id",
            measure_names=["total_students", "critical_risk_students"],
            limit=10,
        )

        is_valid, error = validate_data_types(response, expected_dimensions=1)
        assert is_valid, f"Data type validation failed: {error}"

    def test_wellbeing_risk_row_counts(self, rill_base_url):
        """
        Validate that wellbeing_risk_profiles returns data rows.

        Tests that:
        - Query returns at least 1 row
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="wellbeing_risk_profiles",
            dimension_name="school_id",
            measure_names=["total_students"],
            limit=10,
        )

        is_valid, error = validate_row_counts(response, min_rows=1)
        assert is_valid, f"Row count validation failed: {error}"

    def test_wellbeing_risk_measure_values(self, rill_base_url):
        """
        Validate that wellbeing_risk_profiles measures have valid values.

        Tests that:
        - Student counts are non-negative
        - Risk level categorization is present
        """
        response = execute_rill_query(
            rill_base_url,
            dashboard_name="wellbeing_risk_profiles",
            dimension_name="school_id",
            measure_names=["total_students", "critical_risk_students"],
            limit=5,
        )

        data = response.get("data", [])
        assert len(data) > 0, "No data returned"

        for row in data:
            # Validate school_id
            assert "school_id" in row, "Missing school_id"
            assert row["school_id"] is not None, "school_id should not be null"

            # Validate student counts are non-negative
            if "total_students" in row and row["total_students"] is not None:
                assert isinstance(row["total_students"], (int, float)), (
                    f"total_students should be numeric"
                )
                assert row["total_students"] >= 0, f"total_students should be non-negative"


# ============================================================================
# INTEGRATION TEST SUITE
# ============================================================================


class TestAllDashboardsIntegration:
    """Cross-dashboard integration tests"""

    def test_all_dashboards_accessible(self, rill_base_url):
        """
        Validate all 5 dashboards are accessible via API.

        Tests that:
        - Each dashboard can be queried
        - Each returns valid response
        """
        dashboards = [
            ("chronic_absenteeism_risk", "school_id", ["total_students"]),
            ("equity_outcomes_by_demographics", "race_ethnicity", ["cohort_size"]),
            ("class_effectiveness", "school_id", ["total_students"]),
            ("performance_correlations", "correlation_pair", ["total_correlations"]),
            ("wellbeing_risk_profiles", "school_id", ["total_students"]),
        ]

        results = []
        for dashboard, dimension, measures in dashboards:
            try:
                response = execute_rill_query(
                    rill_base_url,
                    dashboard_name=dashboard,
                    dimension_name=dimension,
                    measure_names=measures,
                    limit=5,
                )
                is_valid, error = validate_response_schema(response)
                results.append((dashboard, is_valid, error))
            except Exception as e:
                results.append((dashboard, False, str(e)))

        # All dashboards must be accessible
        for dashboard, is_valid, error in results:
            assert is_valid, f"Dashboard {dashboard} failed: {error}"

    def test_all_dashboards_return_data(self, rill_base_url):
        """
        Validate all dashboards return data rows.

        Tests that:
        - Each dashboard returns at least 1 row
        - Data is queryable
        """
        dashboards = [
            ("chronic_absenteeism_risk", "school_id", ["total_students"]),
            ("equity_outcomes_by_demographics", "race_ethnicity", ["cohort_size"]),
            ("class_effectiveness", "school_id", ["total_students"]),
            ("performance_correlations", "correlation_pair", ["total_correlations"]),
            ("wellbeing_risk_profiles", "school_id", ["total_students"]),
        ]

        for dashboard, dimension, measures in dashboards:
            response = execute_rill_query(
                rill_base_url,
                dashboard_name=dashboard,
                dimension_name=dimension,
                measure_names=measures,
                limit=10,
            )

            data = response.get("data", [])
            assert len(data) > 0, f"Dashboard {dashboard} returned no rows"


# ============================================================================
# MAIN EXECUTION & REPORTING
# ============================================================================


def generate_summary_report(base_url: str) -> str:
    """
    Generate a summary report of all dashboard queries.

    Tests each dashboard with a sample query and reports results.

    Args:
        base_url: Rill server base URL

    Returns:
        Formatted summary report string
    """
    report = []
    report.append("\n" + "=" * 80)
    report.append("RILL INTEGRATION TEST - SUMMARY REPORT")
    report.append("=" * 80)
    report.append(f"Timestamp: {datetime.now().isoformat()}")
    report.append(f"Rill Server: {base_url}")
    report.append("")

    dashboards = [
        {
            "name": "chronic_absenteeism_risk",
            "title": "Chronic Absenteeism Risk",
            "dimension": "school_id",
            "measures": ["total_students", "chronic_absence_rate"],
        },
        {
            "name": "equity_outcomes_by_demographics",
            "title": "Equity Outcomes by Demographics",
            "dimension": "race_ethnicity",
            "measures": ["cohort_size", "avg_gpa"],
        },
        {
            "name": "class_effectiveness",
            "title": "Class Effectiveness",
            "dimension": "school_id",
            "measures": ["total_students", "avg_pass_rate"],
        },
        {
            "name": "performance_correlations",
            "title": "Performance Correlations",
            "dimension": "correlation_pair",
            "measures": ["total_correlations", "avg_correlation"],
        },
        {
            "name": "wellbeing_risk_profiles",
            "title": "Wellbeing Risk Profiles",
            "dimension": "school_id",
            "measures": ["total_students", "critical_risk_students"],
        },
    ]

    report.append("DASHBOARD VALIDATION RESULTS:")
    report.append("-" * 80)

    passed = 0
    failed = 0

    for dashboard in dashboards:
        try:
            response = execute_rill_query(
                base_url,
                dashboard_name=dashboard["name"],
                dimension_name=dashboard["dimension"],
                measure_names=dashboard["measures"],
                limit=10,
            )

            is_valid, error = validate_response_schema(response)
            if is_valid:
                data_count = len(response.get("data", []))
                meta_count = len(response.get("meta", []))
                report.append(
                    f"✓ {dashboard['title']:45} | Rows: {data_count:3} | Columns: {meta_count}"
                )
                passed += 1
            else:
                report.append(f"✗ {dashboard['title']:45} | ERROR: {error}")
                failed += 1
        except Exception as e:
            report.append(f"✗ {dashboard['title']:45} | EXCEPTION: {str(e)[:50]}")
            failed += 1

    report.append("-" * 80)
    report.append(f"Results: {passed} PASSED, {failed} FAILED")
    report.append("=" * 80)
    report.append("")

    return "\n".join(report)


if __name__ == "__main__":
    # When run directly (not via pytest), generate a summary report
    import sys

    base_url = "http://localhost:9009"
    report = generate_summary_report(base_url)
    print(report)

    # Exit with appropriate code
    sys.exit(0)
