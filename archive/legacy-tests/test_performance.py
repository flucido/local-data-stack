#!/usr/bin/env python3
"""
Performance Testing Suite for Dashboards
Validates response times meet SLA targets: p95 <2s, p99 <3s
"""

import os
import time
import duckdb
import statistics
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
import threading


class PerformanceTest:
    def __init__(
        self,
        duckdb_path: str = os.getenv(
            "DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb"
        ),
    ):
        self.db_path = duckdb_path
        self.results = {"queries": {}}
        self.lock = threading.Lock()

    def run_query(self, name: str, query: str) -> float:
        """Run query and return execution time in milliseconds"""
        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            start = time.time()
            conn.execute(query).fetchall()
            duration = (time.time() - start) * 1000
            conn.close()
            return duration
        except Exception as e:
            print(f"✗ Query '{name}' failed: {e}")
            return None

    def benchmark_query(self, name: str, query: str, iterations: int = 10) -> Dict:
        """Benchmark a query with multiple iterations"""
        print(f"\nBenchmarking: {name}")
        print(f"  Query: {query[:80]}...")

        times = []
        for i in range(iterations):
            duration = self.run_query(name, query)
            if duration is not None:
                times.append(duration)
                print(f"    Run {i + 1}: {duration:.2f}ms", end="")
                if (i + 1) % 5 == 0:
                    print()
                else:
                    print(", ", end="")

        if not times:
            return {"error": "All queries failed"}

        times.sort()
        result = {
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": times[int(len(times) * 0.95) - 1] if len(times) >= 20 else times[-1],
            "p99": times[int(len(times) * 0.99) - 1]
            if len(times) >= 100
            else times[-1],
            "iterations": len(times),
        }

        return result

    def test_chronic_absenteeism_queries(self):
        """Test chronic absenteeism dashboard queries"""
        print("\n" + "=" * 70)
        print("CHRONIC ABSENTEEISM DASHBOARD QUERIES")
        print("=" * 70)

        queries = {
            "At-Risk Count": """
                SELECT COUNT(DISTINCT student_key) as count
                FROM main_analytics.v_chronic_absenteeism_risk
                WHERE risk_level IN ('High', 'Critical')
            """,
            "Chronic Rate": """
                SELECT ROUND(
                    COUNT(CASE WHEN risk_level != 'Low' THEN 1 END) * 100.0 / 
                    COUNT(DISTINCT student_key), 1) as rate
                FROM main_analytics.v_chronic_absenteeism_risk
            """,
            "Risk Distribution": """
                SELECT risk_level, COUNT(DISTINCT student_key) as count
                FROM main_analytics.v_chronic_absenteeism_risk
                GROUP BY risk_level
            """,
            "Top At-Risk Students": """
                SELECT student_key, risk_level, attendance_rate_30d
                FROM main_analytics.v_chronic_absenteeism_risk
                WHERE risk_level IN ('High', 'Critical')
                ORDER BY chronic_absenteeism_risk_score DESC
                LIMIT 50
            """,
            "By Grade Analysis": """
                SELECT grade_level, COUNT(DISTINCT student_key) as total,
                    COUNT(CASE WHEN risk_level = 'High' THEN 1 END) as high_count
                FROM main_analytics.v_chronic_absenteeism_risk
                GROUP BY grade_level
            """,
        }

        for name, query in queries.items():
            result = self.benchmark_query(name, query)
            with self.lock:
                self.results["queries"][name] = result

    def test_wellbeing_queries(self):
        """Test wellbeing dashboard queries"""
        print("\n" + "=" * 70)
        print("WELLBEING DASHBOARD QUERIES")
        print("=" * 70)

        queries = {
            "Wellbeing Profile Count": """
                SELECT COUNT(*) as count
                FROM main_analytics.v_wellbeing_risk_profiles
            """,
            "Wellbeing Sample": """
                SELECT * FROM main_analytics.v_wellbeing_risk_profiles LIMIT 100
            """,
        }

        for name, query in queries.items():
            result = self.benchmark_query(name, query)
            with self.lock:
                self.results["queries"][name] = result

    def test_equity_queries(self):
        """Test equity outcomes queries"""
        print("\n" + "=" * 70)
        print("EQUITY OUTCOMES QUERIES")
        print("=" * 70)

        queries = {
            "Equity Data Load": """
                SELECT COUNT(*) as count
                FROM main_analytics.v_equity_outcomes_by_demographics
            """
        }

        for name, query in queries.items():
            result = self.benchmark_query(name, query)
            with self.lock:
                self.results["queries"][name] = result

    def test_all_queries(self):
        """Run all performance tests"""
        print("\n" + "=" * 70)
        print("DASHBOARD PERFORMANCE TEST SUITE")
        print("SLA Targets: p95 < 2000ms, p99 < 3000ms")
        print("=" * 70)

        self.test_chronic_absenteeism_queries()
        self.test_wellbeing_queries()
        self.test_equity_queries()

        return self.analyze_results()

    def analyze_results(self) -> bool:
        """Analyze results against SLA"""
        print("\n" + "=" * 70)
        print("PERFORMANCE ANALYSIS")
        print("=" * 70)

        sla_p95 = 2000
        sla_p99 = 3000
        all_passed = True

        for query_name, metrics in self.results["queries"].items():
            if "error" in metrics:
                print(f"\n✗ {query_name}: FAILED")
                print(f"  Error: {metrics['error']}")
                all_passed = False
                continue

            print(f"\n{query_name}:")
            print(f"  Min:    {metrics['min']:.2f}ms")
            print(f"  Max:    {metrics['max']:.2f}ms")
            print(f"  Mean:   {metrics['mean']:.2f}ms")
            print(f"  Median: {metrics['median']:.2f}ms")
            print(
                f"  P95:    {metrics['p95']:.2f}ms {'✓' if metrics['p95'] < sla_p95 else '✗'}"
            )
            print(
                f"  P99:    {metrics['p99']:.2f}ms {'✓' if metrics['p99'] < sla_p99 else '✗'}"
            )

            if metrics["p95"] >= sla_p95 or metrics["p99"] >= sla_p99:
                all_passed = False

        print("\n" + "=" * 70)
        if all_passed:
            print("✓ ALL QUERIES PASSED SLA TARGETS")
        else:
            print("⚠ SOME QUERIES EXCEEDED SLA TARGETS - NEEDS OPTIMIZATION")
        print("=" * 70)

        return all_passed


def main():
    """Run performance tests"""
    tester = PerformanceTest()
    success = tester.test_all_queries()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
