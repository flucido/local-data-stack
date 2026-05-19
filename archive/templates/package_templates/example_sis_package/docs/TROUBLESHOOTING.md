# Troubleshooting Guide

## Overview

This guide provides solutions for common issues encountered when using the example SIS package. Issues are organized by category: connection problems, data validation errors, transformation issues, performance bottlenecks, and debugging techniques.

---

## Connection and Credential Issues

### Issue: "Connection refused" error when extracting from SIS

**Error Message**:
```
psycopg2.OperationalError: could not connect to server: Connection refused
Is the server running on host "sis.example.com" and accepting TCP connections on port 5432?
```

**Root Causes**:
1. SIS database server is down or unreachable
2. Firewall blocking connection on specified port
3. Incorrect hostname or IP address in `extraction_config.yaml`
4. Port number is incorrect or not exposed
5. Network connectivity issue (DNS resolution, VPN, etc.)

**Solutions**:

1. **Verify server is running**:
   ```bash
   # Test connectivity to host
   ping sis.example.com
   
   # Test if port is open
   nc -zv sis.example.com 5432
   
   # For SQL Server on port 1433
   nc -zv sis.example.com 1433
   ```

2. **Check extraction_config.yaml**:
   ```yaml
   # Correct format:
   database:
     host: "sis.example.com"      # hostname or IP
     port: 5432                   # PostgreSQL default
     database: "sis_prod"
     username: "extract_user"
     password: "${SIS_DB_PASSWORD}"  # from environment variable
   
   # Common mistakes:
   # - Trailing whitespace: host: "sis.example.com "
   # - Wrong port: port: "5432" (should be integer)
   # - Missing environment variable: no SIS_DB_PASSWORD set
   ```

3. **Verify credentials**:
   ```bash
   # Test with psql (PostgreSQL)
   psql -h sis.example.com -p 5432 -U extract_user -d sis_prod
   
   # Test with sqlcmd (SQL Server)
   sqlcmd -S sis.example.com,1433 -U extract_user -P $SIS_DB_PASSWORD
   
   # Test with sqlplus (Oracle)
   sqlplus extract_user/$SIS_DB_PASSWORD@sis.example.com:1521/sis_prod
   ```

4. **Check firewall and network**:
   - Ask network admin to whitelist extraction server IP
   - Ensure VPN is connected if on remote network
   - Check if SIS requires IP-based authentication

5. **Test with timeout**:
   ```yaml
   database:
     host: "sis.example.com"
     port: 5432
     timeout: 30        # increase from default 5 seconds
     connect_timeout: 60  # for initial connection
   ```

---

### Issue: "Invalid credentials" error

**Error Message**:
```
psycopg2.OperationalError: FATAL: password authentication failed for user "extract_user"
```

**Root Causes**:
1. Wrong username or password in `extraction_config.yaml`
2. Environment variable not set or has wrong value
3. Credentials contain special characters that need escaping
4. User account is disabled in SIS
5. User doesn't have SELECT permission on required tables

**Solutions**:

1. **Verify environment variables are set**:
   ```bash
   # Check if variable exists
   echo $SIS_DB_PASSWORD
   
   # If empty, set it
   export SIS_DB_PASSWORD="your_password_here"
   
   # Verify it's set correctly
   env | grep SIS_DB
   ```

2. **Check for special characters**:
   ```bash
   # Password with special characters needs escaping in YAML
   # ✗ WRONG:
   password: "P@ssw0rd!#$%"
   
   # ✓ CORRECT - use environment variable:
   password: "${SIS_DB_PASSWORD}"
   
   # ✓ CORRECT - escape special characters:
   password: "P@ssw0rd!#$%"  # Actually works in YAML, but use env var for security
   ```

3. **Verify user permissions**:
   ```sql
   -- As database admin, check user permissions
   SELECT grantee, privilege_type 
   FROM information_schema.role_table_grants 
   WHERE table_name IN ('students', 'courses', 'enrollment', 'attendance', 'academic_records')
   AND grantee = 'extract_user';
   
   -- Result should show SELECT permission for all required tables
   -- If not, grant permissions:
   GRANT SELECT ON TABLE students, courses, enrollment, attendance, academic_records 
   TO extract_user;
   ```

4. **Reset password or request new account**:
   - Contact SIS administrator
   - Request account with SELECT-only permission
   - Ensure account is enabled and active

---

### Issue: "SSL connection error" or certificate validation failed

**Error Message**:
```
psycopg2.OperationalError: SSLMODE=require but the server does not support SSL
```

**Root Causes**:
1. SIS requires SSL but configuration doesn't specify it
2. SIS doesn't require SSL but configuration enforces it
3. SSL certificate is invalid or expired
4. CA certificate is not installed

**Solutions**:

1. **Enable SSL in configuration**:
   ```yaml
   database:
     host: "sis.example.com"
     port: 5432
     sslmode: "require"          # or "prefer", "disable", "allow"
     sslcert: "/path/to/client.crt"
     sslkey: "/path/to/client.key"
     sslrootcert: "/path/to/ca.crt"
   ```

2. **SSL modes explained**:
   - `require`: SSL mandatory, validate certificate (default)
   - `prefer`: Try SSL first, fall back to non-SSL
   - `allow`: Try non-SSL first, fall back to SSL
   - `disable`: No SSL connection
   - `verify-ca`: SSL with CA certificate validation
   - `verify-full`: SSL with full certificate validation

3. **Verify certificate**:
   ```bash
   # Check certificate expiry
   openssl x509 -in /path/to/ca.crt -text -noout | grep -A2 "Not"
   
   # If expired, request updated certificate from SIS admin
   
   # Test SSL connection
   openssl s_client -connect sis.example.com:5432 -CAfile /path/to/ca.crt
   ```

4. **For self-signed certificates**:
   ```yaml
   database:
     sslmode: "require"
     sslrootcert: "/path/to/self-signed.crt"  # use verify-ca or verify-full
   ```

---

## Data Validation Errors

### Issue: "NULL values in required field" error during transformation

**Error Message**:
```
ValueError: Required field 'student_id' contains 13 NULL values
Cannot transform with NULLs in primary key
```

**Root Causes**:
1. SIS extract query is missing WHERE clause to filter NULLs
2. Student records are incomplete or corrupted in SIS
3. SIS allows NULLs in field but schema marks as required
4. Data quality issue in upstream SIS

**Solutions**:

1. **Update extraction query to filter NULLs**:
   ```yaml
   extraction:
     query: |
       SELECT student_id, first_name, last_name, date_of_birth
       FROM students
       WHERE student_id IS NOT NULL
         AND first_name IS NOT NULL
         AND last_name IS NOT NULL
   ```

2. **Check which fields have NULLs**:
   ```sql
   -- Profile NULL values in source data
   SELECT 
     'students' as table_name,
     COUNT(*) as total_rows,
     COUNT(CASE WHEN student_id IS NULL THEN 1 END) as student_id_nulls,
     COUNT(CASE WHEN first_name IS NULL THEN 1 END) as first_name_nulls,
     COUNT(CASE WHEN last_name IS NULL THEN 1 END) as last_name_nulls
   FROM students;
   ```

3. **Update SCHEMAS.md to allow NULLs if appropriate**:
   ```yaml
   # In transformation_config.yaml
   validation_rules:
     students:
       - field: student_id
         rule_type: null_check
         nullable: false       # changed from false to true if nulls are acceptable
       - field: middle_name
         rule_type: null_check
         nullable: true        # middle name can be null
   ```

4. **Handle NULLs in transformation**:
   ```python
   # In transformation code
   df['first_name'].fillna('UNKNOWN', inplace=True)  # Replace NULLs with default
   
   # Or filter out rows with NULLs
   df = df.dropna(subset=['student_id', 'first_name', 'last_name'])
   ```

---

### Issue: "Type conversion failed" error

**Error Message**:
```
ValueError: Unable to parse '2024-13-45' as type 'date'
Expected format: YYYY-MM-DD, got invalid date
```

**Root Causes**:
1. Date format in SIS doesn't match expected format
2. Invalid date values in source (month > 12, day > 31)
3. Data encoding issue (UTF-8 vs ASCII)
4. Field contains mixed data types

**Solutions**:

1. **Specify date format in configuration**:
   ```yaml
   transformation:
     field_mappings:
       - sis_column: "birth_date"
         standard_column: "date_of_birth"
         data_type: "date"
         format: "YYYY-MM-DD"        # ISO 8601 standard
         alternate_formats:          # fallback formats to try
           - "MM/DD/YYYY"
           - "DD/MM/YYYY"
           - "YYYY/MM/DD"
   ```

2. **Test date parsing**:
   ```python
   import pandas as pd
   
   # Try parsing with multiple formats
   sample_dates = ['2024-05-15', '05/15/2024', '15/05/2024']
   for date_str in sample_dates:
       try:
           parsed = pd.to_datetime(date_str)
           print(f"✓ {date_str} → {parsed}")
       except:
           print(f"✗ {date_str} failed to parse")
   ```

3. **Validate dates in source query**:
   ```sql
   -- Find invalid dates
   SELECT student_id, birth_date
   FROM students
   WHERE birth_date > CURRENT_DATE
      OR birth_date < '1900-01-01'
      OR EXTRACT(YEAR FROM birth_date) NOT BETWEEN 1900 AND EXTRACT(YEAR FROM CURRENT_DATE);
   ```

4. **Handle invalid dates**:
   ```python
   # Coerce to datetime, replacing invalid dates with NaT
   df['date_of_birth'] = pd.to_datetime(
       df['date_of_birth'], 
       format='%Y-%m-%d',
       errors='coerce'  # invalid dates become NaT
   )
   
   # Check how many were coerced
   print(f"Converted {df['date_of_birth'].isna().sum()} invalid dates to NaT")
   ```

---

### Issue: "Duplicate values in unique field" error

**Error Message**:
```
ValueError: Field 'student_id' should be unique but found 3 duplicate values
Duplicates: S12345, S67890, S11111
```

**Root Causes**:
1. SIS data has duplicate records
2. Student transferred between schools (appears twice)
3. Data extraction includes deleted records
4. SIS administrator error (manual data entry)

**Solutions**:

1. **Identify duplicate sources**:
   ```sql
   -- Find duplicate student IDs
   SELECT student_id, COUNT(*) as count
   FROM students
   GROUP BY student_id
   HAVING COUNT(*) > 1
   ORDER BY count DESC;
   
   -- See details of duplicates
   SELECT student_id, first_name, last_name, enrollment_date, status
   FROM students
   WHERE student_id IN (
       SELECT student_id FROM students GROUP BY student_id HAVING COUNT(*) > 1
   )
   ORDER BY student_id;
   ```

2. **Update extraction query to remove duplicates**:
   ```yaml
   extraction:
     query: |
       SELECT DISTINCT ON (student_id) student_id, first_name, last_name
       FROM students
       WHERE status = 'ACTIVE'
       ORDER BY student_id, enrollment_date DESC;  -- keeps most recent
   ```

3. **Configure deduplication in transformation**:
   ```yaml
   transformation:
     deduplication:
       enabled: true
       key_fields: ['student_id']      # columns that define uniqueness
       keep: 'last'                    # keep first or last occurrence
       sort_by: 'enrollment_date'      # sort before deduplication
   ```

4. **Handle duplicates in code**:
   ```python
   # Remove duplicates, keeping last occurrence
   df = df.drop_duplicates(subset=['student_id'], keep='last')
   
   # Or keep only active enrollment status
   df = df[df['status'] == 'ACTIVE'].drop_duplicates(subset=['student_id'])
   ```

---

## Transformation Issues

### Issue: "Field mapping error" - column not found

**Error Message**:
```
KeyError: "Column 'birth_dt' not found in source data
Available columns: student_id, first_name, last_name, dob_date, email"
```

**Root Causes**:
1. Column name in `extraction_config.yaml` doesn't match actual SIS column
2. SIS schema changed and column was renamed
3. Typo in field mapping configuration
4. Column is only available in certain environments

**Solutions**:

1. **Verify actual column names**:
   ```sql
   -- List all columns in students table
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_name = 'students'
   ORDER BY ordinal_position;
   
   -- For SQL Server
   SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
   FROM INFORMATION_SCHEMA.COLUMNS
   WHERE TABLE_NAME = 'students'
   ORDER BY ORDINAL_POSITION;
   ```

2. **Update field mapping**:
   ```yaml
   # ✗ WRONG:
   field_mappings:
     - sis_column: "birth_dt"        # doesn't exist
       standard_column: "date_of_birth"
   
   # ✓ CORRECT:
   field_mappings:
     - sis_column: "dob_date"        # correct column name
       standard_column: "date_of_birth"
   ```

3. **Test extraction query directly**:
   ```python
   import pandas as pd
   
   # Connect and extract
   df = pd.read_sql(extraction_query, connection)
   print(df.columns.tolist())  # list actual column names
   print(df.head())            # preview data
   ```

4. **Create environment-specific configurations**:
   ```yaml
   # extraction_config.dev.yaml
   database:
     host: "dev-sis.example.com"
     database: "sis_dev"
   extraction:
     query: |
       SELECT student_id, first_name, last_name, dob_date  -- dev environment
       FROM students
   
   # extraction_config.prod.yaml
   extraction:
     query: |
       SELECT student_id, first_name, last_name, birth_dt  -- prod environment
       FROM students
   ```

---

### Issue: "Invalid pseudonymization rule" error

**Error Message**:
```
ValueError: Privacy rule 'invalid_hash' not recognized
Valid options: 'hash', 'mask', 'no-op'
```

**Root Causes**:
1. Typo in privacy rule name in `transformation_config.yaml`
2. Using old rule name from previous version
3. Rule name case-sensitive mismatch

**Solutions**:

1. **Check valid privacy rules**:
   ```yaml
   # Valid rules:
   privacy_rules:
     - field: student_id
       rule: hash      # ✓ correct
     
     - field: first_name
       rule: mask      # ✓ correct
     
     - field: grade_level
       rule: no-op     # ✓ correct
   
   # ✗ Invalid:
   # rule: Hash        (wrong case)
   # rule: HASH        (wrong case)
   # rule: hash_md5    (doesn't exist)
   # rule: anonymize   (doesn't exist)
   ```

2. **Verify transformation_config.yaml syntax**:
   ```yaml
   # Check YAML is valid
   transformation:
     privacy_rules:
       students:
         - field: student_id
           rule: hash              # lowercase, no quotes needed
         - field: first_name
           rule: mask
   ```

---

### Issue: "Aggregation produced NaN values"

**Error Message**:
```
Warning: Stage 3 aggregation resulted in NaN values
Field 'avg_gpa' contains NaN in 27 rows
```

**Root Causes**:
1. Aggregating empty groups (no records match filter)
2. Division by zero in calculated fields
3. All values in group are NULL
4. Aggregation function incompatible with data type

**Solutions**:

1. **Handle empty groups**:
   ```python
   # Filter out groups with insufficient data
   group_stats = df.groupby('grade_level').agg({
       'gpa': ['mean', 'count']
   })
   
   # Keep only groups with at least 10 students
   group_stats = group_stats[group_stats[('gpa', 'count')] >= 10]
   ```

2. **Fill NaN values**:
   ```python
   # Replace NaN with 0 or group mean
   df['avg_gpa'].fillna(0, inplace=True)
   
   # Or use forward fill within groups
   df['avg_gpa'] = df.groupby('grade_level')['avg_gpa'].fillna(method='ffill')
   ```

3. **Add data quality filters in aggregation query**:
   ```sql
   -- Stage 3 aggregation with data quality checks
   SELECT 
     grade_level,
     COUNT(DISTINCT student_id) as student_count,
     AVG(gpa) FILTER (WHERE gpa IS NOT NULL) as avg_gpa,
     MIN(gpa) as min_gpa,
     MAX(gpa) as max_gpa,
     COUNT(CASE WHEN gpa IS NULL THEN 1 END) as null_gpa_count
   FROM enrollment
   WHERE gpa IS NOT NULL
   GROUP BY grade_level
   HAVING COUNT(DISTINCT student_id) >= 10  -- minimum group size
   ```

---

## Performance Issues

### Issue: Extraction is very slow (> 10 minutes for 50k records)

**Error Message**:
```
WARNING: Extraction took 687 seconds (11.5 minutes)
Expected time for 50,000 records: 30-60 seconds
```

**Root Causes**:
1. No database indexes on extracted columns
2. Extraction query is not optimized
3. Network latency between extraction and SIS
4. SIS database server is slow/overloaded

**Solutions**:

1. **Check if columns are indexed**:
   ```sql
   -- PostgreSQL: check indexes
   SELECT indexname, indexdef 
   FROM pg_indexes 
   WHERE tablename IN ('students', 'courses', 'enrollment', 'attendance', 'academic_records');
   
   -- SQL Server: check indexes
   SELECT 
     OBJECT_NAME(i.object_id) AS table_name,
     i.name AS index_name,
     c.name AS column_name
   FROM sys.indexes i
   JOIN sys.index_columns ic ON i.object_id = ic.object_id
   JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
   WHERE OBJECT_NAME(i.object_id) IN ('students', 'courses', 'enrollment', 'attendance', 'academic_records')
   ```

2. **Optimize extraction query**:
   ```yaml
   # ✗ SLOW: Full table scan, no WHERE clause
   extraction:
     query: |
       SELECT * FROM students;
   
   # ✓ FAST: Indexed WHERE clause, specific columns
   extraction:
     query: |
       SELECT student_id, first_name, last_name, date_of_birth, email
       FROM students
       WHERE enrollment_status = 'ACTIVE'
         AND created_date >= '2024-01-01';  -- limit historical data
   ```

3. **Request SIS admin to add indexes**:
   ```sql
   -- Indexes SIS admin should create for fast extraction
   CREATE INDEX idx_students_status ON students(enrollment_status) WHERE enrollment_status = 'ACTIVE';
   CREATE INDEX idx_enrollment_term ON enrollment(term) WHERE completion_status = 'Completed';
   CREATE INDEX idx_attendance_date ON attendance(date) WHERE date >= CURRENT_DATE - INTERVAL '180 days';
   ```

4. **Reduce extracted volume**:
   ```yaml
   extraction:
     # Extract only recent data, not entire history
     query: |
       SELECT * FROM students
       WHERE enrollment_status IN ('ACTIVE', 'GRADUATED')
         AND last_updated_date >= CURRENT_DATE - INTERVAL '365 days'
   
     # Or extract incrementally
     batch_mode: delta
     delta_column: last_updated_date
     delta_since_file: /tmp/last_extract_date.txt
   ```

---

### Issue: Transformation is running out of memory

**Error Message**:
```
MemoryError: Unable to allocate 8.5 GB for array with shape (50000000,) 
Process killed due to excessive memory usage
```

**Root Causes**:
1. Loading entire dataset into memory at once
2. Creating multiple copies of large DataFrames
3. Hash calculation on billions of values
4. Insufficient system RAM

**Solutions**:

1. **Process data in batches**:
   ```yaml
   transformation:
     batch_size: 10000           # process 10k records at a time
     memory_limit: "4GB"         # max memory per batch
   ```

2. **Update transformation code to use chunks**:
   ```python
   import pandas as pd
   
   # Read in chunks
   chunk_size = 10000
   chunks = []
   
   for chunk in pd.read_csv('stage1_data.csv', chunksize=chunk_size):
       # Transform each chunk
       chunk['student_id_hashed'] = chunk['student_id'].apply(hash_function)
       chunks.append(chunk)
   
   # Concatenate results
   df_transformed = pd.concat(chunks, ignore_index=True)
   ```

3. **Use generators instead of lists**:
   ```python
   # ✗ WRONG: creates list of all 50k records in memory
   hashed_ids = [hash_function(sid) for sid in students]
   
   # ✓ CORRECT: uses generator, one at a time
   def hash_generator(students):
       for sid in students:
           yield hash_function(sid)
   ```

4. **Filter unnecessary columns early**:
   ```python
   # ✗ WRONG: loads all columns, then drops
   df = pd.read_csv('stage1_data.csv')  # 500MB
   df = df[['student_id', 'gpa']]       # keep 10MB
   
   # ✓ CORRECT: only load needed columns
   df = pd.read_csv('stage1_data.csv', usecols=['student_id', 'gpa'])  # 10MB
   ```

---

## Storage and Disk Space Issues

### Issue: "No space left on device" during Stage 2B transformation

**Error Message**:
```
OSError: [Errno 28] No space left on device: '/data/stage2b/...'
Available space: 0 GB
```

**Root Causes**:
1. Stage 1 or Stage 2A data not cleaned up
2. Log files accumulating
3. Temporary transformation files not deleted
4. Storage capacity insufficient for all stages

**Solutions**:

1. **Check disk space**:
   ```bash
   # Check space usage
   df -h /data/
   
   # Check by directory
   du -sh /data/stage1/
   du -sh /data/stage2a/
   du -sh /data/stage2b/
   du -sh /data/stage3/
   du -sh /data/logs/
   
   # Find largest files
   find /data -type f -size +100M -exec ls -lh {} \; | sort -k5 -hr | head -10
   ```

2. **Clean up old data**:
   ```bash
   # Remove Stage 1 data older than 7 days
   find /data/stage1/ -type f -mtime +7 -delete
   
   # Remove Stage 2A data older than 30 days
   find /data/stage2a/ -type f -mtime +30 -delete
   
   # Remove Stage 2B data older than 90 days (keep recent for validation)
   find /data/stage2b/ -type f -mtime +90 -delete
   ```

3. **Clean up logs**:
   ```bash
   # Archive and remove old logs
   gzip /data/logs/*.log.*
   find /data/logs/ -name "*.gz" -mtime +30 -delete
   
   # Or set up log rotation in config
   ```

4. **Expand storage capacity**:
   - Calculate data per extraction: (record count × average record size)
   - 3 stages need: Stage1 + Stage2A + Stage2B space
   - Example: 5M students × 2KB = 10GB per stage × 3 stages = 30GB minimum
   - Increase storage based on growth projections

---

### Issue: Retention policies not working (old data not deleted)

**Error Message**:
```
Warning: Records from 2020 still exist in Stage 2B
Expected purge date was 2024-01-15
```

**Root Causes**:
1. Retention job is not scheduled or disabled
2. Retention policy not configured
3. Permissions issue preventing deletion
4. Backup/archive process interfering

**Solutions**:

1. **Check if retention job is scheduled**:
   ```bash
   # For cron-based jobs
   crontab -l | grep retention
   
   # For Airflow DAGs
   airflow dags list | grep purge
   
   # For manual job
   ls -la /scripts/run_retention.sh
   ```

2. **Verify retention configuration**:
   ```yaml
   retention_policies:
     stage_1:
       retention_days: 2555        # 7 years
       purge_enabled: true
       soft_delete: false          # actually delete, not mark deleted
     
     stage_2a:
       retention_days: 1825        # 5 years
       purge_enabled: true
     
     stage_2b:
       retention_days: 1095        # 3 years
       purge_enabled: true
   ```

3. **Run retention job manually**:
   ```bash
   # Test retention policies
   python scripts/run_retention.py --dry-run --verbose
   
   # Actually run retention
   python scripts/run_retention.py --force
   
   # Check what was deleted
   python scripts/run_retention.py --report
   ```

4. **Restore from backups if needed**:
   ```bash
   # Retention policy too aggressive?
   # Restore from backup
   restore_from_backup.sh /backups/stage2b_2024-01-15.tar.gz /data/stage2b/
   ```

---

## Logging and Debugging

### Issue: "Can't find the error in logs"

**Solutions**:

1. **Enable debug logging**:
   ```yaml
   logging:
     level: DEBUG              # verbose output
     format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
     log_file: "/data/logs/sis_package_debug.log"
     max_file_size_mb: 100
     backup_count: 10          # keep 10 rotated log files
   ```

2. **Search logs effectively**:
   ```bash
   # Find errors in logs
   grep -i error /data/logs/*.log | head -20
   
   # Find specific transformation error
   grep -i "student_id" /data/logs/*.log | grep -i error
   
   # Show context around error
   grep -B5 -A5 "MemoryError" /data/logs/*.log
   
   # Get most recent errors
   tail -100 /data/logs/sis_package_debug.log | grep ERROR
   ```

3. **Enable audit logging for privacy**:
   ```yaml
   audit_logging:
     enabled: true
     log_all_access: true      # log every data access
     log_query_details: true   # log SQL queries
     log_file: "/data/logs/audit.log"
   ```

4. **Monitor extraction in real-time**:
   ```bash
   # Watch extraction progress
   tail -f /data/logs/sis_package_debug.log
   
   # Or write to syslog for monitoring
   python scripts/extract_sis.py 2>&1 | tee -a /data/logs/extract_$(date +%Y%m%d).log
   ```

---

### Issue: Reproducing errors in development environment

**Solutions**:

1. **Create test datasets**:
   ```bash
   # Export sample of production data to dev
   psql -h sis-prod.example.com -U extract_user -d sis_prod \
     -c "COPY (SELECT * FROM students LIMIT 1000) TO STDOUT" \
     | psql -h sis-dev.example.com -U extract_user -d sis_dev \
     -c "COPY students FROM STDIN"
   ```

2. **Use test notebooks for debugging**:
   - See `notebooks/03_quality_validation.py` for profiling
   - Run with sample data to identify issues
   - Test transformations step-by-step

3. **Create minimal reproducible example**:
   ```python
   # Create small test case
   import pandas as pd
   
   # Reproduce issue with minimal data
   df_test = pd.DataFrame({
       'student_id': ['S123', None, 'S456'],
       'first_name': ['John', 'Jane', 'Bob'],
       'gpa': [3.9, 3.2, 'invalid']
   })
   
   # Test transformation
   try:
       df_result = transform_record(df_test)
   except Exception as e:
       print(f"Error: {e}")
       print(f"Failed row: {df_test.iloc[1]}")
   ```

---

## Common Configuration Mistakes

| Mistake | Issue | Fix |
|---------|-------|-----|
| Missing file extensions | Config not loaded | Use `.yaml` not `.yml` |
| Trailing whitespace in URLs | Connection fails | Remove spaces: `"host.com "` |
| Quotes in YAML values | Type error | Use `'` or `"` correctly: `"value"` |
| Environment variable typo | Config value empty | Check: `echo $VAR_NAME` |
| Port as string not integer | Type error | Use `5432` not `"5432"` |
| Windows line endings (CRLF) | Parse errors | Convert to Unix (LF): `dos2unix file.yaml` |
| Missing required field | Validation error | Check schema requirements |
| Boolean as string | Type mismatch | Use `true/false` not `"true"` |

---

## Contact and Escalation

If you've worked through this guide and still have issues:

1. **Check documentation**:
   - ARCHITECTURE.md - System design overview
   - DATA_DICTIONARY.md - Field definitions
   - PRIVACY_RULES.md - Privacy configuration
   - SCHEMAS.md - Data model

2. **Review package README.md**:
   - Setup instructions
   - Quick start guide
   - Environment setup

3. **Contact support**:
   - SIS vendor support for database issues
   - District data admin for field mapping
   - Security team for privacy questions

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Data Operations Team  
**Next Review**: Quarterly or as issues are resolved
