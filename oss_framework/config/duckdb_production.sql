-- DuckDB Production Configuration
-- Apply before each session for optimal performance and stability
-- Usage: duckdb <database_path> < duckdb_production.sql
--
-- Based on production best practices from:
-- - https://medium.com/@sparknp1/duckdb-in-prod-the-checklist-nobody-brags-about-1f9b503f9cbd
-- - https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d
-- - https://toolstac.com/tool/duckdb/performance-optimization

-- ============================================================================
-- MEMORY MANAGEMENT
-- ============================================================================

-- Set memory limit to 90% (NOT 95%+) to prevent OS lockups
-- This leaves headroom for OS operations and prevents OOM kills
SET memory_limit = '90%';

-- Alternative: Set explicit memory limit for containerized environments
-- SET memory_limit = '4GB';  -- Uncomment for Docker/K8s with known limits


-- ============================================================================
-- THREAD OPTIMIZATION
-- ============================================================================

-- Use physical cores only (disable hyperthreading for analytical workloads)
-- Default is auto-detect, but explicit control is safer in production
SET threads TO 4;  -- Adjust based on your CPU (use os.cpu_count() // 2)

-- For CPU-bound workloads, match physical core count
-- For I/O-bound workloads, can use logical cores


-- ============================================================================
-- TEMPORARY STORAGE
-- ============================================================================

-- Configure explicit temp directory for out-of-core operations
-- DuckDB spills to disk when memory limit is reached
SET temp_directory = '/tmp/duckdb_temp';

-- Ensure this directory exists and has sufficient space
-- Recommended: SSD/NVMe storage for best spill performance


-- ============================================================================
-- DURABILITY & WAL
-- ============================================================================

-- WAL (Write-Ahead Log) checkpointing for crash recovery
-- Checkpoint every 1000 transactions (balance between durability and performance)
PRAGMA wal_autocheckpoint=1000;

-- Alternative: Immediate mode (slower writes, maximum durability)
-- PRAGMA synchronous=FULL;


-- ============================================================================
-- QUERY PROFILING
-- ============================================================================

-- Enable query profiling for performance debugging
SET enable_profiling = 'query_tree';  -- Options: 'query_tree', 'json', 'no_output'

-- To view profiling output after a query:
-- PRAGMA show_last_profile;

-- Disable in production for performance (re-enable for debugging):
-- SET enable_profiling = 'no_output';


-- ============================================================================
-- PERFORMANCE OPTIMIZATIONS
-- ============================================================================

-- Enable object cache for frequently accessed objects
SET enable_object_cache = true;

-- Preserve insertion order (can improve query performance for ordered data)
SET preserve_insertion_order = true;

-- Enable parallel CSV reading (for data loading)
SET experimental_parallel_csv = true;


-- ============================================================================
-- NETWORK & REMOTE ACCESS (S3/GCS)
-- ============================================================================

-- Configure S3 region (if using S3 data sources)
-- SET s3_region='us-west-2';

-- Configure HTTP timeout for remote reads (default: 30000ms)
SET http_timeout = 60000;  -- 60 seconds for large files

-- Enable HTTP retries
SET http_retries = 3;


-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify configuration (these should return your settings)
SELECT current_setting('memory_limit') as memory_limit;
SELECT current_setting('threads') as threads;
SELECT current_setting('temp_directory') as temp_directory;
SELECT current_setting('enable_object_cache') as object_cache_enabled;

-- Display all settings
-- PRAGMA show_all_settings;
