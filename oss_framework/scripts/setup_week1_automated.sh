#!/bin/bash
# Week 1-2 Automated Setup Script
# This script sets up the entire data foundation once clarification questions are answered
# Usage: bash oss_framework/scripts/setup_week1_automated.sh

set -e

echo "=========================================="
echo "OSS Framework - Week 1-2 Automated Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OSS_FRAMEWORK_DIR="$PROJECT_DIR/oss_framework"
DATA_DIR="$OSS_FRAMEWORK_DIR/data"
SCRIPTS_DIR="$OSS_FRAMEWORK_DIR/scripts"
LOGS_DIR="$OSS_FRAMEWORK_DIR/logs"

echo -e "${YELLOW}[1/10]${NC} Checking prerequisites..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

# Check for pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 not found. Please install pip${NC}"
    exit 1
fi
echo -e "${GREEN}✅ pip found${NC}"

# Create directories
echo -e "${YELLOW}[2/10]${NC} Creating directory structure..."
mkdir -p "$DATA_DIR/stage1" "$DATA_DIR/stage2" "$DATA_DIR/stage3"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$LOGS_DIR"
echo -e "${GREEN}✅ Directories created${NC}"

# Create Python virtual environment
echo -e "${YELLOW}[3/10]${NC} Creating Python virtual environment..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}[4/10]${NC} Installing Python dependencies..."
source "$PROJECT_DIR/venv/bin/activate"

# Install requirements
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet \
    duckdb \
    pandas \
    requests \
    python-dotenv \
    pytest \
    pytest-cov \
    pydantic \
    sqlalchemy \
    dbt-duckdb \
    dagster \
    dagster-webserver \
    metabase

echo -e "${GREEN}✅ Python dependencies installed${NC}"

# Check .env file
echo -e "${YELLOW}[5/10]${NC} Checking environment configuration..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    
    cat > "$PROJECT_DIR/.env.template" << 'EOF'
# Aeries API Configuration
# Choose ONE authentication method:

# Option A: API Key Authentication (Recommended)
AERIES_API_URL=https://api.aeries.com/v5
AERIES_API_KEY=your_api_key_here
AERIES_AUTH_METHOD=api_key

# Option B: OAuth2 Authentication
# AERIES_CLIENT_ID=your_client_id_here
# AERIES_CLIENT_SECRET=your_client_secret_here
# AERIES_AUTH_METHOD=oauth2

# Option C: Direct Database Access
# AERIES_DB_HOST=your_sql_server_host
# AERIES_DB_PORT=1433
# AERIES_DB_DATABASE=aeries_database
# AERIES_DB_USERNAME=your_username
# AERIES_DB_PASSWORD=your_password
# AERIES_AUTH_METHOD=database

# DuckDB Configuration
DUCKDB_DATABASE_PATH=./oss_framework/data/oea.duckdb
DUCKDB_MEMORY_LIMIT=8GB

# Data Lake Paths
STAGE1_PATH=./oss_framework/data/stage1
STAGE2_PATH=./oss_framework/data/stage2
STAGE3_PATH=./oss_framework/data/stage3

# Excel Report Paths (Update based on your locations)
EXCEL_DF_REPORT_PATH=./oss_framework/docs/tech_docs/Requirements/D and F w_504 SE.xlsx
EXCEL_DEMOGRAPHIC_PATH=./oss_framework/docs/tech_docs/Requirements/Demographic Data by Course 24_25.xlsx
EXCEL_RFEP_PATH=./oss_framework/docs/tech_docs/Requirements/RFEP.png

# Excel Update Frequency (set based on CLARIFICATION_QUESTIONS answer)
EXCEL_DF_UPDATE_FREQUENCY=weekly  # Options: daily, weekly, monthly, manual
EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY=static  # Options: daily, weekly, monthly, static
EXCEL_RFEP_UPDATE_FREQUENCY=monthly  # Options: daily, weekly, monthly, manual

# Data Retention & FERPA
DATA_RETENTION_YEARS=5
ARCHIVE_GRADUATED_STUDENTS=true
PSEUDONYMIZATION_LEVEL=full  # Options: full, identified
AUDIT_LOGGING_ENABLED=true

# Dashboard Configuration (will be set after CLARIFICATION_QUESTIONS)
DASHBOARD_PRIORITY_RANKING=1,2,3,4,5  # Comma-separated dashboard order
DASHBOARD_USER_ACCESS_LEVEL=role_based  # Options: role_based, unrestricted

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./oss_framework/logs/oea.log
EOF
    
    echo -e "${YELLOW}📄 Template created at .env.template${NC}"
    echo -e "${YELLOW}❌ REQUIRED: Copy .env.template to .env and fill in your credentials${NC}"
    echo -e "${YELLOW}   cp .env.template .env${NC}"
    echo -e "${YELLOW}   # Edit .env with your Aeries credentials${NC}"
    exit 1
else
    echo -e "${GREEN}✅ .env file found${NC}"
fi

# Verify DuckDB
echo -e "${YELLOW}[6/10]${NC} Testing DuckDB connection..."
python3 << 'PYTHON_TEST'
import duckdb
import os
db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb")
try:
    con = duckdb.connect(db_path)
    result = con.execute("SELECT 1").fetchall()
    print("✅ DuckDB connection successful")
    con.close()
except Exception as e:
    print(f"❌ DuckDB error: {e}")
    exit(1)
PYTHON_TEST

# Create Python modules
echo -e "${YELLOW}[7/10]${NC} Creating Python modules..."

# Create __init__ files
touch "$SCRIPTS_DIR/__init__.py"

# Create requirements.txt if it doesn't exist
if [ ! -f "$OSS_FRAMEWORK_DIR/requirements.txt" ]; then
    cat > "$OSS_FRAMEWORK_DIR/requirements.txt" << 'EOF'
duckdb==1.0.0
pandas==2.0.0
requests==2.31.0
python-dotenv==1.0.0
pytest==7.4.0
pytest-cov==4.1.0
pydantic==2.0.0
sqlalchemy==2.0.0
dbt-duckdb==1.7.0
dagster==1.5.0
dagster-webserver==1.5.0
metabase==0.1.0
EOF
    echo -e "${GREEN}✅ requirements.txt created${NC}"
else
    echo -e "${GREEN}✅ requirements.txt already exists${NC}"
fi

# Create config module
cat > "$SCRIPTS_DIR/config.py" << 'EOF'
"""Configuration management for OSS Framework"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Aeries Configuration
AERIES_API_URL = os.getenv("AERIES_API_URL", "https://api.aeries.com/v5")
AERIES_API_KEY = os.getenv("AERIES_API_KEY")
AERIES_CLIENT_ID = os.getenv("AERIES_CLIENT_ID")
AERIES_CLIENT_SECRET = os.getenv("AERIES_CLIENT_SECRET")
AERIES_AUTH_METHOD = os.getenv("AERIES_AUTH_METHOD", "api_key")

# Database Configuration
AERIES_DB_HOST = os.getenv("AERIES_DB_HOST")
AERIES_DB_PORT = os.getenv("AERIES_DB_PORT", 1433)
AERIES_DB_DATABASE = os.getenv("AERIES_DB_DATABASE")
AERIES_DB_USERNAME = os.getenv("AERIES_DB_USERNAME")
AERIES_DB_PASSWORD = os.getenv("AERIES_DB_PASSWORD")

# DuckDB Configuration
DUCKDB_DATABASE_PATH = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb")
DUCKDB_MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "8GB")

# Data Lake Paths
STAGE1_PATH = Path(os.getenv("STAGE1_PATH", "./oss_framework/data/stage1"))
STAGE2_PATH = Path(os.getenv("STAGE2_PATH", "./oss_framework/data/stage2"))
STAGE3_PATH = Path(os.getenv("STAGE3_PATH", "./oss_framework/data/stage3"))

# Excel Report Paths
EXCEL_DF_REPORT_PATH = os.getenv("EXCEL_DF_REPORT_PATH")
EXCEL_DEMOGRAPHIC_PATH = os.getenv("EXCEL_DEMOGRAPHIC_PATH")
EXCEL_RFEP_PATH = os.getenv("EXCEL_RFEP_PATH")

# Update Frequencies
EXCEL_DF_UPDATE_FREQUENCY = os.getenv("EXCEL_DF_UPDATE_FREQUENCY", "weekly")
EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY = os.getenv("EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY", "static")
EXCEL_RFEP_UPDATE_FREQUENCY = os.getenv("EXCEL_RFEP_UPDATE_FREQUENCY", "monthly")

# Data Retention
DATA_RETENTION_YEARS = int(os.getenv("DATA_RETENTION_YEARS", 5))
ARCHIVE_GRADUATED_STUDENTS = os.getenv("ARCHIVE_GRADUATED_STUDENTS", "true").lower() == "true"

# Pseudonymization
PSEUDONYMIZATION_LEVEL = os.getenv("PSEUDONYMIZATION_LEVEL", "full")
AUDIT_LOGGING_ENABLED = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "./oss_framework/logs/oea.log")

# Create log directory if it doesn't exist
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# Validation
def validate_config():
    """Validate that required configuration is set"""
    errors = []
    
    if AERIES_AUTH_METHOD == "api_key" and not AERIES_API_KEY:
        errors.append("AERIES_API_KEY not set")
    
    if AERIES_AUTH_METHOD == "oauth2" and (not AERIES_CLIENT_ID or not AERIES_CLIENT_SECRET):
        errors.append("AERIES_CLIENT_ID or AERIES_CLIENT_SECRET not set")
    
    if AERIES_AUTH_METHOD == "database" and not all([AERIES_DB_HOST, AERIES_DB_DATABASE]):
        errors.append("Database configuration incomplete")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

if __name__ == "__main__":
    print("Current Configuration:")
    print(f"  Aeries Auth: {AERIES_AUTH_METHOD}")
    print(f"  DuckDB: {DUCKDB_DATABASE_PATH}")
    print(f"  Stage1: {STAGE1_PATH}")
    print(f"  Stage2: {STAGE2_PATH}")
    print(f"  Stage3: {STAGE3_PATH}")
    print(f"  Data Retention: {DATA_RETENTION_YEARS} years")
EOF

echo -e "${GREEN}✅ Python modules created${NC}"

# Create data quality checks
echo -e "${YELLOW}[8/10]${NC} Creating data quality validation module..."

cat > "$SCRIPTS_DIR/data_quality.py" << 'EOF'
"""Data quality validation for OSS Framework"""
import duckdb
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class DataQualityValidator:
    """Validates data quality across all stages"""
    
    def __init__(self, db_path: str):
        self.con = duckdb.connect(db_path)
        self.results = []
    
    def validate_table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        try:
            result = self.con.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
            ).fetchall()
            exists = result[0][0] > 0
            status = "✅" if exists else "❌"
            logger.info(f"{status} Table {table_name}: {'exists' if exists else 'missing'}")
            return exists
        except Exception as e:
            logger.error(f"❌ Error checking table {table_name}: {e}")
            return False
    
    def validate_no_null_ids(self, table_name: str, id_column: str) -> bool:
        """Check for null IDs (data integrity issue)"""
        try:
            result = self.con.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {id_column} IS NULL"
            ).fetchall()
            null_count = result[0][0]
            if null_count == 0:
                logger.info(f"✅ {table_name}.{id_column}: No nulls")
                return True
            else:
                logger.warning(f"❌ {table_name}.{id_column}: {null_count} nulls found")
                return False
        except Exception as e:
            logger.error(f"❌ Error validating {table_name}.{id_column}: {e}")
            return False
    
    def validate_row_count(self, table_name: str, min_rows: int = 0) -> bool:
        """Check table has data"""
        try:
            result = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchall()
            count = result[0][0]
            if count >= min_rows:
                logger.info(f"✅ {table_name}: {count} rows")
                return True
            else:
                logger.warning(f"❌ {table_name}: Only {count} rows (expected >{min_rows})")
                return False
        except Exception as e:
            logger.error(f"❌ Error counting rows in {table_name}: {e}")
            return False
    
    def run_all_validations(self) -> Dict[str, bool]:
        """Run complete validation suite"""
        logger.info("Starting data quality validation...")
        
        validations = {
            "raw_students_exists": self.validate_table_exists("raw_students"),
            "raw_attendance_exists": self.validate_table_exists("raw_attendance"),
            "raw_academic_exists": self.validate_table_exists("raw_academic_records"),
            "raw_discipline_exists": self.validate_table_exists("raw_discipline"),
            "raw_students_no_nulls": self.validate_no_null_ids("raw_students", "student_id"),
            "raw_attendance_data": self.validate_row_count("raw_attendance", min_rows=100),
        }
        
        passed = sum(1 for v in validations.values() if v)
        total = len(validations)
        logger.info(f"Validation complete: {passed}/{total} passed")
        
        return validations
    
    def close(self):
        """Close database connection"""
        self.con.close()
EOF

echo -e "${GREEN}✅ Data quality module created${NC}"

# Create logging setup
echo -e "${YELLOW}[9/10]${NC} Setting up logging..."

cat > "$SCRIPTS_DIR/logging_config.py" << 'EOF'
"""Logging configuration for OSS Framework"""
import logging
import logging.handlers
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

def setup_logging(name: str) -> logging.Logger:
    """Configure logging for a module"""
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(detailed_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    return logger
EOF

echo -e "${GREEN}✅ Logging configured${NC}"

# Create test runner
echo -e "${YELLOW}[10/10]${NC} Creating test infrastructure..."

mkdir -p "$OSS_FRAMEWORK_DIR/tests"
touch "$OSS_FRAMEWORK_DIR/tests/__init__.py"

cat > "$OSS_FRAMEWORK_DIR/tests/test_configuration.py" << 'EOF'
"""Test configuration and environment"""
import pytest
import os
from pathlib import Path

def test_environment_variables():
    """Verify required environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Should have at least one auth method configured
    auth_method = os.getenv("AERIES_AUTH_METHOD")
    assert auth_method in ["api_key", "oauth2", "database"], f"Invalid auth method: {auth_method}"

def test_directories_exist():
    """Verify data directories exist"""
    dirs = [
        "./oss_framework/data/stage1",
        "./oss_framework/data/stage2",
        "./oss_framework/data/stage3",
        "./oss_framework/logs",
    ]
    for dir_path in dirs:
        assert Path(dir_path).exists(), f"Directory not found: {dir_path}"

def test_duckdb_connection():
    """Test DuckDB can connect"""
    import duckdb
    import os
    
    db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb")
    con = duckdb.connect(db_path)
    result = con.execute("SELECT 1").fetchall()
    assert result[0][0] == 1
    con.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
EOF

echo -e "${GREEN}✅ Test infrastructure created${NC}"

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}✅ SETUP COMPLETE${NC}"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo "1. Configure credentials:"
echo "   cp .env.template .env"
echo "   # Edit .env with your Aeries API key or database credentials"
echo ""
echo "2. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Run configuration tests:"
echo "   pytest oss_framework/tests/test_configuration.py -v"
echo ""
echo "4. Answer clarification questions:"
echo "   See: oss_framework/docs/CLARIFICATION_QUESTIONS.md"
echo ""
echo "5. Run Week 1-2 data foundation:"
echo "   python oss_framework/scripts/create_stage1_tables.py"
echo "   python oss_framework/scripts/ingest_aeries_data.py"
echo ""
echo "📚 Documentation: /oss_framework/docs/"
echo "📊 Data Lake: /oss_framework/data/"
echo "📝 Logs: /oss_framework/logs/"
echo ""

exit 0
