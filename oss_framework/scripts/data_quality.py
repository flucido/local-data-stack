"""Data quality validation for OSS Framework"""
import duckdb
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class DataQualityValidator:
    """Validates data quality across all stages"""
    
    def __init__(self, db_path: str):
        self.con = duckdb.connect(db_path)
        self.validation_results = {}
    
    def validate_table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        try:
            result = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchall()
            return len(result) > 0
        except:
            return False
    
    def validate_row_count(self, table_name: str, min_count: int = 1) -> bool:
        """Validate minimum row count"""
        try:
            count = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            passed = count >= min_count
            logger.info(f"  Table {table_name}: {count} rows (min: {min_count}) - {'✅' if passed else '❌'}")
            return passed
        except Exception as e:
            logger.error(f"  Table {table_name}: Error - {str(e)}")
            return False
    
    def run_all_validations(self) -> Dict[str, bool]:
        """Run all quality checks on Stage 1 tables"""
        logger.info("Running data quality validations...")
        
        tables = [
            'raw_students',
            'raw_attendance',
            'raw_academic_records',
            'raw_discipline',
            'raw_enrollment'
        ]
        
        for table in tables:
            if self.validate_table_exists(table):
                self.validation_results[table] = self.validate_row_count(table, min_count=1)
            else:
                logger.warning(f"  Table {table}: Does not exist")
                self.validation_results[table] = False
        
        return self.validation_results
    
    def close(self):
        """Close database connection"""
        self.con.close()

if __name__ == "__main__":
    validator = DataQualityValidator("./oss_framework/data/oea.duckdb")
    results = validator.run_all_validations()
    passed = sum(1 for v in results.values() if v)
    print(f"\n✅ Validation complete: {passed}/{len(results)} tables passed")
    validator.close()
