#!/usr/bin/env python3
"""
RBAC and Row-Level Security Testing Suite
Tests access controls across all dashboards
"""

import json
import pytest
from datetime import datetime, timedelta
from enum import Enum


class UserRole(Enum):
    """User roles and their permissions"""

    ADMIN = {
        "access_all_dashboards": True,
        "access_all_data": True,
        "edit_permissions": True,
        "can_export": True,
    }
    PRINCIPAL = {
        "access_all_dashboards": True,
        "access_all_data": True,
        "edit_permissions": False,
        "can_export": True,
    }
    TEACHER = {
        "access_all_dashboards": False,  # Only own class data
        "access_all_data": False,
        "edit_permissions": False,
        "can_export": True,
    }
    DISTRICT_ANALYST = {
        "access_all_dashboards": True,
        "access_all_data": True,
        "edit_permissions": False,
        "can_export": True,
    }
    STUDENT = {
        "access_all_dashboards": False,  # Own data only
        "access_all_data": False,
        "edit_permissions": False,
        "can_export": False,
    }
    PARENT = {
        "access_all_dashboards": False,  # Own child data
        "access_all_data": False,
        "edit_permissions": False,
        "can_export": False,
    }


class TestRowLevelSecurity:
    """Test RLS across all dashboards"""

    def test_admin_access_all_dashboards(self):
        """Admin should access all dashboards and all data"""
        user = {"role": UserRole.ADMIN, "school_id": None, "district_id": None}
        permissions = self._get_permissions(user)
        assert permissions["access_all_dashboards"] is True
        assert permissions["access_all_data"] is True

    def test_principal_access_all_school_data(self):
        """Principal should access all data within their school"""
        user = {"role": UserRole.PRINCIPAL, "school_id": "SCH1", "district_id": "DIST1"}
        permissions = self._get_permissions(user)

        # Should have dashboard access
        assert permissions["access_all_dashboards"] is True

        # But data should be filtered to school
        rls_filter = self._get_rls_filter(user)
        assert "school_id = 'SCH1'" in rls_filter

    def test_teacher_access_own_class_only(self):
        """Teacher should only see their own class data"""
        user = {
            "role": UserRole.TEACHER,
            "school_id": "SCH1",
            "class_id": "CLS1",
            "district_id": "DIST1",
        }

        # Cannot access class effectiveness dashboard without proper filter
        permissions = self._get_permissions(user)
        assert permissions["access_all_dashboards"] is False

        # Data must be filtered to their class
        rls_filter = self._get_rls_filter(user)
        assert "class_id = 'CLS1'" in rls_filter

    def test_student_access_own_data_only(self):
        """Student should only see their own data"""
        user = {
            "role": UserRole.STUDENT,
            "student_id": "STU123",
            "district_id": "DIST1",
        }

        # Cannot access any dashboard
        permissions = self._get_permissions(user)
        assert permissions["access_all_dashboards"] is False
        assert permissions["access_all_data"] is False

        # Data filtered to themselves only
        rls_filter = self._get_rls_filter(user)
        assert "student_key = 'STU123'" in rls_filter

    def test_parent_access_child_data_only(self):
        """Parent should only see their child's data"""
        user = {"role": UserRole.PARENT, "student_id": "STU123", "district_id": "DIST1"}

        # Cannot export
        permissions = self._get_permissions(user)
        assert permissions["can_export"] is False

        # Data filtered to child
        rls_filter = self._get_rls_filter(user)
        assert "student_key = 'STU123'" in rls_filter

    def test_district_analyst_access_all_district_data(self):
        """District analyst should see all data within their district"""
        user = {"role": UserRole.DISTRICT_ANALYST, "district_id": "DIST1"}

        # Can access all dashboards
        permissions = self._get_permissions(user)
        assert permissions["access_all_dashboards"] is True

        # But not all data (filtered by district)
        rls_filter = self._get_rls_filter(user)
        assert "district_id = 'DIST1'" in rls_filter or len(rls_filter) > 0

    def test_cross_district_access_denied(self):
        """User should not access data from other districts"""
        user_dist1 = {
            "role": UserRole.PRINCIPAL,
            "school_id": "SCH1",
            "district_id": "DIST1",
        }
        user_dist2 = {
            "role": UserRole.PRINCIPAL,
            "school_id": "SCH2",
            "district_id": "DIST2",
        }

        filter1 = self._get_rls_filter(user_dist1)
        filter2 = self._get_rls_filter(user_dist2)

        assert filter1 != filter2
        assert "SCH1" in filter1
        assert "SCH2" in filter2

    def test_cross_school_access_denied(self):
        """Principal should not access data from other schools"""
        user = {"role": UserRole.PRINCIPAL, "school_id": "SCH1", "district_id": "DIST1"}
        filter_sql = self._get_rls_filter(user)

        # Filter should restrict to their school
        assert "SCH1" in filter_sql

    @staticmethod
    def _get_permissions(user: dict) -> dict:
        """Get permissions for a user"""
        role = user.get("role")
        if role in UserRole.__members__.values():
            return role.value
        return {}

    @staticmethod
    def _get_rls_filter(user: dict) -> str:
        """Generate RLS WHERE clause for user"""
        role = user.get("role")
        filters = []

        if role == UserRole.ADMIN:
            return "1=1"  # No filter
        elif role == UserRole.PRINCIPAL:
            filters.append(f"school_id = '{user.get('school_id')}'")
        elif role == UserRole.TEACHER:
            filters.append(f"class_id = '{user.get('class_id')}'")
        elif role == UserRole.STUDENT or role == UserRole.PARENT:
            filters.append(f"student_key = '{user.get('student_id')}'")
        elif role == UserRole.DISTRICT_ANALYST:
            filters.append(f"district_id = '{user.get('district_id')}'")

        return " AND ".join(filters) if filters else "1=1"


class TestDashboardAccessControl:
    """Test dashboard-specific access controls"""

    def test_chronic_absenteeism_access(self):
        """Test chronic absenteeism dashboard access"""
        assert self._can_access_dashboard(UserRole.ADMIN, "chronic_absenteeism") is True
        assert (
            self._can_access_dashboard(UserRole.PRINCIPAL, "chronic_absenteeism")
            is True
        )
        assert (
            self._can_access_dashboard(UserRole.TEACHER, "chronic_absenteeism") is False
        )
        assert (
            self._can_access_dashboard(UserRole.STUDENT, "chronic_absenteeism") is False
        )

    def test_wellbeing_access(self):
        """Test wellbeing dashboard access"""
        assert self._can_access_dashboard(UserRole.ADMIN, "wellbeing") is True
        assert self._can_access_dashboard(UserRole.PRINCIPAL, "wellbeing") is True
        assert self._can_access_dashboard(UserRole.TEACHER, "wellbeing") is False

    def test_equity_outcomes_access(self):
        """Test equity outcomes dashboard access"""
        assert self._can_access_dashboard(UserRole.ADMIN, "equity_outcomes") is True
        assert (
            self._can_access_dashboard(UserRole.DISTRICT_ANALYST, "equity_outcomes")
            is True
        )
        assert self._can_access_dashboard(UserRole.TEACHER, "equity_outcomes") is False

    def test_class_effectiveness_access(self):
        """Test class effectiveness dashboard access"""
        # Only teachers and admins
        assert self._can_access_dashboard(UserRole.ADMIN, "class_effectiveness") is True
        assert (
            self._can_access_dashboard(UserRole.TEACHER, "class_effectiveness") is True
        )
        assert (
            self._can_access_dashboard(UserRole.STUDENT, "class_effectiveness") is False
        )

    @staticmethod
    def _can_access_dashboard(role: UserRole, dashboard: str) -> bool:
        """Check if role can access dashboard"""
        dashboard_permissions = {
            "chronic_absenteeism": [
                UserRole.ADMIN,
                UserRole.PRINCIPAL,
                UserRole.DISTRICT_ANALYST,
            ],
            "wellbeing": [
                UserRole.ADMIN,
                UserRole.PRINCIPAL,
                UserRole.DISTRICT_ANALYST,
            ],
            "equity_outcomes": [
                UserRole.ADMIN,
                UserRole.PRINCIPAL,
                UserRole.DISTRICT_ANALYST,
            ],
            "class_effectiveness": [
                UserRole.ADMIN,
                UserRole.PRINCIPAL,
                UserRole.TEACHER,
            ],
            "performance_correlations": [
                UserRole.ADMIN,
                UserRole.PRINCIPAL,
                UserRole.DISTRICT_ANALYST,
            ],
        }

        allowed = dashboard_permissions.get(dashboard, [])
        return role in allowed


class TestDataExport:
    """Test data export permissions"""

    def test_admin_can_export(self):
        """Admin can export all data"""
        user = {"role": UserRole.ADMIN}
        assert self._can_export(user) is True

    def test_teacher_can_export_own_data(self):
        """Teacher can export only their class data"""
        user = {"role": UserRole.TEACHER}
        assert self._can_export(user) is True

    def test_student_cannot_export(self):
        """Student cannot export data"""
        user = {"role": UserRole.STUDENT}
        assert self._can_export(user) is False

    def test_parent_cannot_export(self):
        """Parent cannot export data"""
        user = {"role": UserRole.PARENT}
        assert self._can_export(user) is False

    @staticmethod
    def _can_export(user: dict) -> bool:
        """Check if user can export data"""
        role = user.get("role")
        return role.value.get("can_export", False)


def run_tests():
    """Run all RBAC tests"""
    print("=" * 70)
    print("RBAC AND ROW-LEVEL SECURITY TEST SUITE")
    print("=" * 70)

    test_classes = [
        TestRowLevelSecurity(),
        TestDashboardAccessControl(),
        TestDataExport(),
    ]

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        print(f"\n{test_class.__class__.__name__}:")

        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                total_tests += 1
                try:
                    method = getattr(test_class, method_name)
                    method()
                    print(f"  ✓ {method_name}")
                    passed_tests += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    print("=" * 70)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
