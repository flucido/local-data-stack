#!/bin/bash
# Week 1-2 Automated Setup Script
# Usage: bash oss_framework/scripts/setup_week1_automated.sh

set -euo pipefail

echo "=========================================="
echo "OSS Framework - Automated Environment Setup"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OSS_FRAMEWORK_DIR="$PROJECT_DIR/oss_framework"
DATA_DIR="$OSS_FRAMEWORK_DIR/data"
SCRIPTS_DIR="$OSS_FRAMEWORK_DIR/scripts"
LOGS_DIR="$OSS_FRAMEWORK_DIR/logs"

echo -e "${YELLOW}[1/6]${NC} Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

echo -e "${YELLOW}[2/6]${NC} Creating directory structure..."
mkdir -p "$DATA_DIR/stage1" "$DATA_DIR/stage2" "$DATA_DIR/stage3"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$LOGS_DIR"
echo -e "${GREEN}✅ Directories created${NC}"

echo -e "${YELLOW}[3/6]${NC} Creating Python virtual environment (.venv)..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
    echo -e "${GREEN}✅ Virtual environment created at .venv${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists at .venv${NC}"
fi

echo -e "${YELLOW}[4/6]${NC} Installing editable package dependencies..."
source "$PROJECT_DIR/.venv/bin/activate"
pip install --quiet --upgrade pip setuptools wheel
(cd "$PROJECT_DIR" && pip install -e ".[dev,nl-query]")
echo -e "${GREEN}✅ Python dependencies installed${NC}"

echo -e "${YELLOW}[5/6]${NC} Checking environment configuration..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found.${NC}"
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        echo -e "${YELLOW}❌ REQUIRED: Copy .env.example to .env and fill in your salts/keys:${NC}"
        echo -e "${YELLOW}   cp .env.example .env${NC}"
    fi
    exit 1
else
    echo -e "${GREEN}✅ .env file found${NC}"
fi

echo -e "${YELLOW}[6/6]${NC} Testing DuckDB connection..."
python3 << 'PYTHON_TEST'
import os
import duckdb

db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")
con = duckdb.connect(db_path)
try:
    result = con.execute("SELECT 1").fetchall()
    assert result[0][0] == 1
    print("✅ DuckDB connection successful")
finally:
    con.close()
PYTHON_TEST

echo ""
echo "=========================================="
echo -e "${GREEN}✅ SETUP COMPLETE${NC}"
echo "=========================================="
echo "Activate virtual environment: source .venv/bin/activate"
echo "Run pipeline: python scripts/run_pipeline.py"
exit 0
