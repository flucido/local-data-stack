#!/usr/bin/env python3
"""
Comprehensive data quality profiling for Parquet data across all 7 Aeries domains.
Uses DuckDB for efficient querying without loading entire files into memory.
"""

import duckdb
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import os

# Domain mappings (domain_output_name -> parquet_path)
DOMAINS = {
    "students": "oss_framework/data/stage1/aeries/students/year=2025-2026/part-000.parquet",
    "attendance": "oss_framework/data/stage1/aeries/attendance_transformed/year=2025-2026/part-000.parquet",
    "discipline": "oss_framework/data/stage1/aeries/discipline_transformed/year=2025-2026/part-000.parquet",
    "enrollment": "oss_framework/data/stage1/aeries/enrollment/year=2025-2026/part-000.parquet",
    "programs": "oss_framework/data/stage1/aeries/programs/year=2025-2026/part-000.parquet",
    "gpa": "oss_framework/data/stage1/aeries/gpa/year=2025-2026/part-000.parquet",
    "grades": "oss_framework/data/stage1/aeries/grades_transformed/year=2025-2026/part-000.parquet",
}

# Critical PII fields to profile
PII_FIELDS = {
    "students": ["StudentID", "FirstName", "LastName", "StudentEmailAddress", "BirthDate", 
                 "HomePhone", "StudentMobilePhone", "MailingAddressLine1", "MailingAddressLine2",
                 "MailingAddressCity", "MailingAddressState", "MailingAddressZipCode"],
    "attendance": [],
    "discipline": [],
    "enrollment": [],
    "programs": [],
    "gpa": [],
    "grades": [],
}

# Critical business fields to check
CRITICAL_FIELDS = {
    "students": ["StudentID", "CorrespondenceLanguageCode", "MailingAddressZipCode"],
    "attendance": ["StudentID", "AttendanceDate"],
    "discipline": ["StudentID", "IncidentDate"],
    "enrollment": ["StudentID", "CourseNumber"],
    "programs": ["StudentID", "ProgramCode"],
    "gpa": ["StudentID", "GPA"],
    "grades": ["StudentID", "CourseNumber", "MarkingPeriodCode"],
}


class ParquetQualityProfiler:
    """Profile data quality for Parquet files"""
    
    def __init__(self):
        self.con = duckdb.connect(":memory:")
        self.results = {}
        
    def profile_domain(self, domain: str, parquet_path: str) -> Dict[str, Any]:
        """Profile a single domain's Parquet file"""
        print(f"\n📊 Profiling {domain}...", flush=True)
        
        if not os.path.exists(parquet_path):
            print(f"  ❌ File not found: {parquet_path}")
            return {"status": "error", "message": f"File not found: {parquet_path}"}
        
        try:
            profile = {
                "domain": domain,
                "file_path": parquet_path,
                "timestamp": datetime.now().isoformat(),
                "file_size_bytes": os.path.getsize(parquet_path),
            }
            
            # Get basic stats
            profile["row_count"] = self._get_row_count(parquet_path)
            profile["column_count"] = self._get_column_count(parquet_path)
            profile["columns"] = self._get_column_names(parquet_path)
            
            # Get schema with types
            profile["schema"] = self._get_schema(parquet_path)
            
            # Analyze missing values
            profile["missing_values"] = self._analyze_missing_values(domain, parquet_path)
            
            # Analyze critical fields
            profile["critical_fields"] = self._analyze_critical_fields(domain, parquet_path)
            
            # Analyze PII fields (if applicable)
            if domain in PII_FIELDS and PII_FIELDS[domain]:
                profile["pii_analysis"] = self._analyze_pii_fields(domain, parquet_path)
            
            # Check for duplicates
            if "StudentID" in profile["columns"]:
                profile["duplicates"] = self._check_duplicates(parquet_path)
            
            # Value distribution for key fields
            profile["distributions"] = self._analyze_distributions(domain, parquet_path)
            
            print(f"  ✅ {profile['row_count']:,} rows, {profile['column_count']} columns")
            
            return profile
            
        except Exception as e:
            print(f"  ❌ Error profiling {domain}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}
    
    def _get_row_count(self, parquet_path: str) -> int:
        """Get total row count"""
        result = self.con.execute(
            f"SELECT COUNT(*) as cnt FROM read_parquet('{parquet_path}')"
        ).fetchall()
        return result[0][0]
    
    def _get_column_count(self, parquet_path: str) -> int:
        """Get column count"""
        result = self.con.execute(f"DESCRIBE '{parquet_path}'").fetchall()
        return len(result)
    
    def _get_column_names(self, parquet_path: str) -> List[str]:
        """Get all column names"""
        result = self.con.execute(f"DESCRIBE '{parquet_path}'").fetchall()
        return [row[0] for row in result]
    
    def _get_schema(self, parquet_path: str) -> Dict[str, str]:
        """Get schema (column -> type mapping)"""
        result = self.con.execute(f"DESCRIBE '{parquet_path}'").fetchall()
        return {row[0]: row[1] for row in result}
    
    def _analyze_missing_values(self, domain: str, parquet_path: str) -> Dict[str, Any]:
        """Analyze null/missing values across all columns"""
        columns = self._get_column_names(parquet_path)
        total_rows = self._get_row_count(parquet_path)
        
        missing_analysis = {
            "total_rows": total_rows,
            "columns_with_nulls": {},
            "critical_nulls": {},
        }
        
        critical_fields = CRITICAL_FIELDS.get(domain, [])
        
        for col in columns:
            try:
                null_count = self.con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{parquet_path}') WHERE \"{col}\" IS NULL"
                ).fetchone()[0]
                
                if null_count > 0:
                    null_pct = (null_count / total_rows) * 100
                    missing_analysis["columns_with_nulls"][col] = {
                        "null_count": null_count,
                        "null_percentage": round(null_pct, 2),
                    }
                    
                    # Flag critical fields with nulls
                    if col in critical_fields:
                        missing_analysis["critical_nulls"][col] = {
                            "null_count": null_count,
                            "null_percentage": round(null_pct, 2),
                            "severity": "HIGH" if null_pct > 10 else "MEDIUM",
                        }
            except Exception as e:
                # Skip columns that can't be analyzed
                pass
        
        return missing_analysis
    
    def _analyze_critical_fields(self, domain: str, parquet_path: str) -> Dict[str, Any]:
        """Deep analysis of critical business fields"""
        critical_fields = CRITICAL_FIELDS.get(domain, [])
        columns = self._get_column_names(parquet_path)
        
        analysis = {}
        
        for field in critical_fields:
            if field not in columns:
                continue
            
            try:
                field_analysis = {
                    "column_name": field,
                    "found": True,
                }
                
                # Get type
                schema = self._get_schema(parquet_path)
                field_analysis["data_type"] = schema.get(field, "unknown")
                
                # Get nulls
                null_count = self.con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{parquet_path}') WHERE \"{field}\" IS NULL"
                ).fetchone()[0]
                total_rows = self._get_row_count(parquet_path)
                field_analysis["null_count"] = null_count
                field_analysis["null_pct"] = round((null_count / total_rows) * 100, 2)
                
                # Get distinct count
                distinct = self.con.execute(
                    f"SELECT COUNT(DISTINCT \"{field}\") FROM read_parquet('{parquet_path}')"
                ).fetchone()[0]
                field_analysis["distinct_count"] = distinct
                
                # Get sample values
                if field_analysis["data_type"].startswith("VARCHAR"):
                    samples = self.con.execute(
                        f'SELECT DISTINCT "{field}" FROM read_parquet(\'{parquet_path}\') WHERE "{field}" IS NOT NULL LIMIT 5'
                    ).fetchall()
                    field_analysis["sample_values"] = [s[0] for s in samples]
                
                analysis[field] = field_analysis
                
            except Exception as e:
                analysis[field] = {"error": str(e)}
        
        return analysis
    
    def _analyze_pii_fields(self, domain: str, parquet_path: str) -> Dict[str, Any]:
        """Analyze PII fields for completeness and patterns"""
        pii_fields = PII_FIELDS.get(domain, [])
        columns = self._get_column_names(parquet_path)
        total_rows = self._get_row_count(parquet_path)
        
        pii_analysis = {
            "total_students": total_rows,
            "pii_fields_found": {},
            "completeness_by_field": {},
            "recommendations": [],
        }
        
        for field in pii_fields:
            if field not in columns:
                pii_analysis["pii_fields_found"][field] = False
                pii_analysis["recommendations"].append(f"Missing PII field: {field}")
                continue
            
            pii_analysis["pii_fields_found"][field] = True
            
            try:
                # Count non-null values
                non_null = self.con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{parquet_path}') WHERE \"{field}\" IS NOT NULL"
                ).fetchone()[0]
                
                completeness_pct = (non_null / total_rows) * 100
                pii_analysis["completeness_by_field"][field] = {
                    "non_null_count": non_null,
                    "completeness_pct": round(completeness_pct, 2),
                    "missing_count": total_rows - non_null,
                }
                
                if completeness_pct < 100:
                    pii_analysis["recommendations"].append(
                        f"{field}: {100 - completeness_pct:.1f}% missing values"
                    )
                
            except Exception as e:
                pii_analysis["completeness_by_field"][field] = {"error": str(e)}
        
        return pii_analysis
    
    def _check_duplicates(self, parquet_path: str) -> Dict[str, Any]:
        """Check for duplicate StudentIDs"""
        try:
            total_rows = self._get_row_count(parquet_path)
            
            distinct_ids = self.con.execute(
                f"SELECT COUNT(DISTINCT StudentID) FROM read_parquet('{parquet_path}')"
            ).fetchone()[0]
            
            duplicates = total_rows - distinct_ids
            
            return {
                "total_rows": total_rows,
                "distinct_student_ids": distinct_ids,
                "duplicate_rows": duplicates,
                "has_duplicates": duplicates > 0,
                "uniqueness_pct": round((distinct_ids / total_rows) * 100, 2),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_distributions(self, domain: str, parquet_path: str) -> Dict[str, Any]:
        """Analyze value distributions for key categorical fields"""
        distributions = {}
        columns = self._get_column_names(parquet_path)
        
        # Select a few key fields to analyze distribution
        key_fields = []
        if domain == "students":
            key_fields = ["CorrespondenceLanguageCode", "Gender", "EthnicityCode"]
        elif domain == "attendance":
            key_fields = ["AttendanceCodeCode"]
        elif domain == "grades":
            key_fields = ["MarkingPeriodCode", "GradeTypeCode"]
        
        for field in key_fields:
            if field not in columns:
                continue
            
            try:
                # Get value distribution
                results = self.con.execute(
                    f'SELECT "{field}", COUNT(*) as cnt FROM read_parquet(\'{parquet_path}\') '
                    f'GROUP BY "{field}" ORDER BY cnt DESC LIMIT 20'
                ).fetchall()
                
                if results:
                    distributions[field] = {
                        "top_values": [
                            {"value": str(r[0]), "count": r[1]} 
                            for r in results
                        ],
                        "total_distinct": len(results),
                    }
            except Exception as e:
                distributions[field] = {"error": str(e)}
        
        return distributions
    
    def profile_all(self) -> Dict[str, Any]:
        """Profile all domains"""
        print("\n" + "="*70)
        print("🔍 DATA QUALITY PROFILING - AeRIES 2025-2026")
        print("="*70)
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "domains_profiled": 0,
            "total_rows": 0,
            "domains": {},
            "issues_found": [],
            "recommendations": [],
        }
        
        for domain, path in DOMAINS.items():
            profile = self.profile_domain(domain, path)
            summary["domains"][domain] = profile
            
            if "status" not in profile or profile["status"] != "error":
                summary["domains_profiled"] += 1
                summary["total_rows"] += profile.get("row_count", 0)
                
                # Collect issues
                if "critical_nulls" in profile and profile["critical_nulls"]:
                    for field, info in profile["critical_nulls"].items():
                        summary["issues_found"].append(
                            f"{domain}.{field}: {info['null_percentage']}% nulls ({info['severity']})"
                        )
                
                if "duplicates" in profile and profile["duplicates"].get("has_duplicates"):
                    dup_count = profile["duplicates"]["duplicate_rows"]
                    summary["issues_found"].append(
                        f"{domain}: {dup_count} duplicate StudentID rows"
                    )
        
        # Summary section
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print("="*70)
        print(f"Domains profiled: {summary['domains_profiled']}")
        print(f"Total rows across all domains: {summary['total_rows']:,}")
        
        if summary["issues_found"]:
            print(f"\n⚠️  Issues Found ({len(summary['issues_found'])}):")
            for issue in summary["issues_found"]:
                print(f"  • {issue}")
        else:
            print("\n✅ No critical issues found")
        
        return summary


def main():
    """Main execution"""
    profiler = ParquetQualityProfiler()
    results = profiler.profile_all()
    
    # Save results to JSON for inspection
    output_file = "data_quality_profile.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Full profile saved to: {output_file}")
    
    # Print summary table
    print("\n" + "="*70)
    print("📈 DOMAIN SUMMARY TABLE")
    print("="*70)
    print(f"{'Domain':<15} {'Rows':>10} {'Columns':>8} {'File Size':>15}")
    print("-" * 70)
    
    for domain, profile in results["domains"].items():
        if "status" in profile and profile["status"] == "error":
            print(f"{domain:<15} {'ERROR':<10} {'-':<8} {'-':<15}")
        else:
            file_size_mb = profile.get("file_size_bytes", 0) / 1024 / 1024
            print(
                f"{domain:<15} {profile.get('row_count', 0):>10,} "
                f"{profile.get('column_count', 0):>8} "
                f"{file_size_mb:>14.2f}MB"
            )


if __name__ == "__main__":
    main()
