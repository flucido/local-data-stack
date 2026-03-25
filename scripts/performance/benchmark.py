#!/usr/bin/env python3
"""
Performance Benchmarking Tool for Local Data Stack

This script benchmarks:
1. Database query performance (DuckDB)
2. Dashboard load times (Rill)
3. Pipeline execution times (stages 1-4)
4. Export performance (Parquet generation)

Usage:
    python3 scripts/performance/benchmark.py                  # Run all benchmarks
    python3 scripts/performance/benchmark.py --database       # Database only
    python3 scripts/performance/benchmark.py --dashboards     # Dashboards only
    python3 scripts/performance/benchmark.py --export         # Export only
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import subprocess
import sys

import duckdb

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DUCKDB_PATH = PROJECT_ROOT / "oss_framework" / "data" / "oea.duckdb"
BENCHMARK_RESULTS_DIR = PROJECT_ROOT / "reports" / "performance"
RILL_PORT = 9009


class PerformanceBenchmark:
    """Performance benchmarking suite"""

    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {},
            "database": {},
            "dashboards": {},
            "pipeline": {},
            "export": {},
        }
        BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def log(self, message: str):
        """Log message to console"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def benchmark_database(self):
        """Benchmark database queries"""
        self.log("=== DATABASE BENCHMARKS ===")

        queries = {
            "student_count": "SELECT COUNT(*) FROM main_core.dim_students",
            "attendance_count": "SELECT COUNT(*) FROM main_core.fact_attendance_daily",
            "grades_count": "SELECT COUNT(*) FROM main_core.fact_grades",
            "discipline_count": "SELECT COUNT(*) FROM main_core.fact_discipline_incidents",
            "student_lookup": """
                SELECT *
                FROM main_core.dim_students
                WHERE student_id = 'STU0001'
            """,
            "attendance_range": """
                SELECT student_id, COUNT(*) as records
                FROM main_core.fact_attendance_daily
                WHERE attendance_date BETWEEN '2025-01-01' AND '2025-06-30'
                GROUP BY student_id
                LIMIT 100
            """,
            "school_summary": """
                SELECT 
                    school_id,
                    COUNT(*) as total_records,
                    AVG(CASE WHEN present_flag THEN 1.0 ELSE 0.0 END) as attendance_rate
                FROM main_core.fact_attendance_daily
                WHERE attendance_date >= '2025-01-01'
                GROUP BY school_id
            """,
            "chronic_risk_dashboard": """
                SELECT *
                FROM main_scoring.score_chronic_absenteeism_risk
                WHERE risk_score > 50
                ORDER BY risk_score DESC
                LIMIT 100
            """,
            "wellbeing_profile": """
                SELECT 
                    w.*,
                    s.first_name,
                    s.last_name,
                    s.grade_level
                FROM main_scoring.score_wellbeing_risk w
                JOIN main_core.dim_students s ON w.student_id = s.student_id
                WHERE w.overall_risk_score > 60
                ORDER BY w.overall_risk_score DESC
                LIMIT 50
            """,
            "analytics_chronic_absenteeism": """
                SELECT * FROM main_analytics.v_chronic_absenteeism_risk
                LIMIT 100
            """,
            "analytics_equity_outcomes": """
                SELECT * FROM main_analytics.v_equity_outcomes_by_demographics
            """,
            "analytics_class_effectiveness": """
                SELECT * FROM main_analytics.v_class_section_comparison
                LIMIT 50
            """,
            "analytics_performance_correlations": """
                SELECT * FROM main_analytics.v_performance_correlations
            """,
            "analytics_wellbeing_risk": """
                SELECT * FROM main_analytics.v_wellbeing_risk_profiles
                LIMIT 100
            """,
        }

        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        query_results = {}

        for query_name, query_sql in queries.items():
            self.log(f"  Testing: {query_name}")
            times = []

            # Run each query 5 times and take average
            for _ in range(5):
                start = time.perf_counter()
                try:
                    result = con.execute(query_sql).fetchall()
                    elapsed = time.perf_counter() - start
                    times.append(elapsed)
                except Exception as e:
                    self.log(f"    ❌ Error: {e}")
                    times.append(-1)
                    break

            if times and times[0] != -1:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                self.log(
                    f"    ✅ Avg: {avg_time * 1000:.2f}ms (min: {min_time * 1000:.2f}ms, max: {max_time * 1000:.2f}ms)"
                )
                query_results[query_name] = {
                    "avg_ms": round(avg_time * 1000, 2),
                    "min_ms": round(min_time * 1000, 2),
                    "max_ms": round(max_time * 1000, 2),
                    "runs": len(times),
                    "status": "success",
                }
            else:
                query_results[query_name] = {
                    "status": "error",
                    "error": "Query failed",
                }

        # Get database size
        db_size_mb = DUCKDB_PATH.stat().st_size / (1024 * 1024)

        # Get table row counts
        tables_info = con.execute("""
            SELECT table_schema, table_name, estimated_size as row_count
            FROM duckdb_tables()
            WHERE table_schema LIKE 'main_%'
            ORDER BY estimated_size DESC
        """).fetchall()

        con.close()

        self.results["database"] = {
            "database_size_mb": round(db_size_mb, 2),
            "tables": [{"schema": t[0], "table": t[1], "rows": t[2]} for t in tables_info],
            "queries": query_results,
        }

    def benchmark_dashboards(self):
        """Benchmark dashboard load times (manual timing required for now)"""
        self.log("=== DASHBOARD BENCHMARKS ===")
        self.log("  ⚠️  Dashboard benchmarking requires manual timing")
        self.log("  Instructions:")
        self.log("    1. Start Rill: cd rill_project && rill start")
        self.log(f"    2. Open http://localhost:{RILL_PORT}")
        self.log("    3. Time how long each dashboard takes to load")
        self.log("")
        self.log("  Expected dashboards:")
        self.log("    - Chronic Absenteeism Risk")
        self.log("    - Equity Outcomes by Demographics")
        self.log("    - Class Effectiveness Analysis")
        self.log("    - Performance Correlations")
        self.log("    - Student Wellbeing Risk Profiles")

        self.results["dashboards"] = {
            "status": "manual_timing_required",
            "instructions": "Time dashboard load in browser",
            "target_load_time_ms": 3000,  # Target: <3 seconds
        }

    def benchmark_export(self):
        """Benchmark Parquet export performance"""
        self.log("=== EXPORT BENCHMARKS ===")

        export_script = PROJECT_ROOT / "scripts" / "export_to_rill.py"
        if not export_script.exists():
            self.log("  ❌ Export script not found")
            self.results["export"] = {"status": "error", "error": "Script not found"}
            return

        # Run export and time it
        self.log("  Running export script...")
        start = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, str(export_script)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            elapsed = time.perf_counter() - start

            if result.returncode == 0:
                self.log(f"  ✅ Export completed in {elapsed:.2f}s")

                # Count exported files
                rill_data_dir = PROJECT_ROOT / "rill_project" / "data"
                parquet_files = list(rill_data_dir.glob("*.parquet"))
                total_size = sum(f.stat().st_size for f in parquet_files)

                self.results["export"] = {
                    "duration_seconds": round(elapsed, 2),
                    "file_count": len(parquet_files),
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "status": "success",
                }
            else:
                self.log(f"  ❌ Export failed: {result.stderr}")
                self.results["export"] = {
                    "status": "error",
                    "error": result.stderr,
                }
        except subprocess.TimeoutExpired:
            self.log("  ❌ Export timeout")
            self.results["export"] = {
                "status": "error",
                "error": "Timeout after 5 minutes",
            }
        except Exception as e:
            self.log(f"  ❌ Export error: {e}")
            self.results["export"] = {
                "status": "error",
                "error": str(e),
            }

    def benchmark_pipeline(self):
        """Benchmark full pipeline execution"""
        self.log("=== PIPELINE BENCHMARKS ===")
        self.log("  ⚠️  Full pipeline benchmarking takes 30+ seconds")
        self.log("  Skipping in favor of component benchmarks")
        self.log("  To benchmark full pipeline manually:")
        self.log("    time python3 scripts/run_pipeline.py --stage all")

        self.results["pipeline"] = {
            "status": "manual_timing_recommended",
            "command": "time python3 scripts/run_pipeline.py --stage all",
        }

    def save_results(self):
        """Save benchmark results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = BENCHMARK_RESULTS_DIR / f"benchmark_{timestamp}.json"

        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)

        self.log(f"\n✅ Results saved to: {output_file}")
        return output_file

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 80)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 80)

        # Database summary
        if "database" in self.results and "queries" in self.results["database"]:
            print("\n📊 DATABASE QUERY PERFORMANCE:")
            queries = self.results["database"]["queries"]
            successful = [q for q in queries.values() if q.get("status") == "success"]
            if successful:
                avg_times = [q["avg_ms"] for q in successful]
                print(f"  • Queries tested: {len(successful)}/{len(queries)}")
                print(f"  • Average query time: {sum(avg_times) / len(avg_times):.2f}ms")
                print(f"  • Fastest query: {min(avg_times):.2f}ms")
                print(f"  • Slowest query: {max(avg_times):.2f}ms")

            # Top 5 slowest queries
            sorted_queries = sorted(
                [(name, q) for name, q in queries.items() if q.get("status") == "success"],
                key=lambda x: x[1]["avg_ms"],
                reverse=True,
            )
            print("\n  Top 5 Slowest Queries:")
            for name, q in sorted_queries[:5]:
                print(f"    {name:40} {q['avg_ms']:8.2f}ms")

        # Database size
        if "database" in self.results:
            db_size = self.results["database"].get("database_size_mb", 0)
            print(f"\n💾 DATABASE SIZE: {db_size:.2f} MB")

        # Export performance
        if "export" in self.results and self.results["export"].get("status") == "success":
            export = self.results["export"]
            print(f"\n📤 EXPORT PERFORMANCE:")
            print(f"  • Duration: {export['duration_seconds']:.2f}s")
            print(f"  • Files created: {export['file_count']}")
            print(f"  • Total size: {export['total_size_mb']:.2f} MB")

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Performance benchmarking tool")
    parser.add_argument("--database", action="store_true", help="Benchmark database queries")
    parser.add_argument("--dashboards", action="store_true", help="Benchmark dashboards")
    parser.add_argument("--export", action="store_true", help="Benchmark exports")
    parser.add_argument("--pipeline", action="store_true", help="Benchmark full pipeline")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks (default)")

    args = parser.parse_args()

    # If no specific benchmark selected, run all
    if not any([args.database, args.dashboards, args.export, args.pipeline]):
        args.all = True

    benchmark = PerformanceBenchmark()

    if args.all or args.database:
        benchmark.benchmark_database()

    if args.all or args.dashboards:
        benchmark.benchmark_dashboards()

    if args.all or args.export:
        benchmark.benchmark_export()

    if args.all or args.pipeline:
        benchmark.benchmark_pipeline()

    output_file = benchmark.save_results()
    benchmark.print_summary()

    print(f"\n📄 Full results: {output_file}")


if __name__ == "__main__":
    main()
