#!/bin/bash
#
# schedule_pipeline.sh - Automated pipeline execution wrapper
#
# This script provides safe execution of the local-data-stack pipeline
# with logging, error handling, and monitoring integration points.
#
# Usage:
#   ./scripts/schedule_pipeline.sh                # Run all stages
#   ./scripts/schedule_pipeline.sh --stage 1      # Run specific stage
#   ./scripts/schedule_pipeline.sh --dry-run      # Test without execution
#

set -euo pipefail

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/oss_framework/logs"
LOG_FILE="${LOG_DIR}/pipeline_scheduled_$(date +%Y%m%d_%H%M%S).log"
LOCK_FILE="${PROJECT_ROOT}/.pipeline.lock"
MAX_RUNTIME_MINUTES=120  # 2 hours timeout

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function: Log message
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

# Function: Cleanup on exit
cleanup() {
    local exit_code=$?
    log "INFO" "Pipeline execution finished with exit code: ${exit_code}"
    
    # Remove lock file
    if [[ -f "$LOCK_FILE" ]]; then
        rm -f "$LOCK_FILE"
        log "INFO" "Released pipeline lock"
    fi
    
    # Send notification (placeholder for future integration)
    if [[ $exit_code -eq 0 ]]; then
        log "INFO" "✅ Pipeline completed successfully"
        # TODO: Send success notification (email, Slack, PagerDuty, etc.)
    else
        log "ERROR" "❌ Pipeline failed with exit code ${exit_code}"
        # TODO: Send failure notification
    fi
    
    exit $exit_code
}

trap cleanup EXIT INT TERM

# Function: Check for running pipeline
check_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE")
        
        if ps -p "$pid" > /dev/null 2>&1; then
            log "ERROR" "Pipeline already running (PID: ${pid})"
            log "ERROR" "If this is incorrect, remove ${LOCK_FILE}"
            exit 1
        else
            log "WARN" "Stale lock file found (PID ${pid} not running), removing"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Create lock file with current PID
    echo $$ > "$LOCK_FILE"
    log "INFO" "Acquired pipeline lock (PID: $$)"
}

# Function: Check environment
check_environment() {
    log "INFO" "Checking environment..."
    
    # Check if .env file exists
    if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
        log "WARN" "No .env file found - pipeline will run in TEST MODE"
        log "WARN" "For production: cp .env.template .env and add credentials"
    fi
    
    # Check Python environment
    if [[ ! -d "${PROJECT_ROOT}/.venv" ]]; then
        log "ERROR" "Virtual environment not found at ${PROJECT_ROOT}/.venv"
        log "ERROR" "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
        exit 1
    fi
    
    # Check DuckDB database
    if [[ ! -f "${PROJECT_ROOT}/oss_framework/data/oea.duckdb" ]]; then
        log "WARN" "DuckDB database not found - will be created on first run"
    fi
    
    # Check Rill installation
    if ! command -v rill &> /dev/null; then
        log "WARN" "Rill not installed - dashboards will not be accessible"
        log "WARN" "Install: curl https://rill.sh | sh"
    fi
    
    log "INFO" "✅ Environment checks passed"
}

# Function: Run pipeline with timeout
run_pipeline() {
    local stage="${1:-all}"
    
    log "INFO" "========================================="
    log "INFO" "Starting pipeline execution: Stage ${stage}"
    log "INFO" "========================================="
    log "INFO" "Project root: ${PROJECT_ROOT}"
    log "INFO" "Log file: ${LOG_FILE}"
    log "INFO" "Max runtime: ${MAX_RUNTIME_MINUTES} minutes"
    
    # Activate virtual environment
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
    
    # Run pipeline with timeout
    if timeout "${MAX_RUNTIME_MINUTES}m" python3 "${PROJECT_ROOT}/scripts/run_pipeline.py" --stage "$stage" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO" "Pipeline completed successfully"
        return 0
    else
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            log "ERROR" "Pipeline timeout after ${MAX_RUNTIME_MINUTES} minutes"
        else
            log "ERROR" "Pipeline failed with exit code: ${exit_code}"
        fi
        return $exit_code
    fi
}

# Function: Post-execution tasks
post_execution() {
    log "INFO" "Running post-execution tasks..."
    
    # Archive old logs (keep last 30 days)
    log "INFO" "Archiving old logs..."
    find "$LOG_DIR" -name "pipeline_scheduled_*.log" -mtime +30 -delete 2>/dev/null || true
    
    # Compress large log files (>10MB)
    find "$LOG_DIR" -name "*.log" -size +10M ! -name "*.gz" -exec gzip {} \; 2>/dev/null || true
    
    # Check database size
    if [[ -f "${PROJECT_ROOT}/oss_framework/data/oea.duckdb" ]]; then
        local db_size
        db_size=$(du -h "${PROJECT_ROOT}/oss_framework/data/oea.duckdb" | cut -f1)
        log "INFO" "Database size: ${db_size}"
    fi
    
    # Check Parquet export size
    if [[ -d "${PROJECT_ROOT}/rill_project/data" ]]; then
        local export_size
        export_size=$(du -sh "${PROJECT_ROOT}/rill_project/data" | cut -f1)
        local file_count
        file_count=$(find "${PROJECT_ROOT}/rill_project/data" -name "*.parquet" | wc -l)
        log "INFO" "Parquet exports: ${file_count} files, ${export_size}"
    fi
    
    log "INFO" "✅ Post-execution tasks complete"
}

# Main execution
main() {
    local stage="all"
    local dry_run=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stage)
                stage="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS]

Options:
    --stage <stage>    Run specific stage (1, 2, 3, 4, or all) [default: all]
    --dry-run          Test without executing pipeline
    --help             Show this help message

Examples:
    $0                        # Run all stages
    $0 --stage 1              # Run Stage 1 only
    $0 --dry-run              # Test environment without running

Environment:
    This script requires:
    - Python virtual environment at ${PROJECT_ROOT}/.venv
    - DuckDB database (will be created if missing)
    - Optional: .env file for production credentials

Logs:
    Execution logs: ${LOG_DIR}/pipeline_scheduled_*.log
    Main application log: ${LOG_DIR}/oea.log

EOF
                exit 0
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                log "ERROR" "Run '$0 --help' for usage information"
                exit 1
                ;;
        esac
    done
    
    if [[ "$dry_run" == true ]]; then
        log "INFO" "DRY RUN MODE - No pipeline execution"
        check_environment
        log "INFO" "Would run: python3 scripts/run_pipeline.py --stage ${stage}"
        exit 0
    fi
    
    # Execute pipeline
    check_lock
    check_environment
    run_pipeline "$stage"
    post_execution
}

# Run main function
main "$@"
