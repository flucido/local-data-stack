# Security Policy

## Overview

The local-data-stack handles sensitive student data and must be deployed with appropriate security measures. This document outlines security best practices, vulnerability reporting, and compliance guidance for FERPA/GDPR.

---

## Reporting Security Vulnerabilities

### Reporting Process

**Please do not report security vulnerabilities through public GitHub issues.**

To report a security vulnerability:

1. **Email**: Send details to `frank@flucido.com` or open a private security advisory on GitHub
2. **GitHub Security Advisory**: Use [GitHub's private vulnerability reporting](https://github.com/flucido/local-data-stack/security/advisories/new)
3. **Response Time**: We aim to respond within 72 hours

### What to Include

Please provide as much detail as possible:

- **Type of vulnerability** (e.g., SQL injection, path traversal, authentication bypass)
- **Affected component** (DuckDB, Rill, dbt, ingestion scripts, etc.)
- **Steps to reproduce** the issue
- **Potential impact** (data exposure, unauthorized access, etc.)
- **Suggested fix** (if available)
- **Proof-of-concept** (if safe to share)

### Disclosure Policy

- We follow [responsible disclosure](https://en.wikipedia.org/wiki/Responsible_disclosure) practices
- We will acknowledge receipt within 72 hours
- We will provide a fix timeline or workaround
- We will coordinate public disclosure after a fix is available
- We will credit reporters in release notes (unless anonymity requested)

---

## Security Best Practices

### 1. Student Data Protection (FERPA/GDPR)

#### Pseudonymization (Required)

**local-data-stack implements pseudonymization by default:**

- **PII Hashing**: Student names, IDs, emails are HMAC-SHA256 hashed (secret salt as the HMAC key)
- **Salted HMAC**: Uses the environment-specific `PII_SALT` (stored in `.env`, >= 16 random characters); digests never reveal the salt
- **Hashed IDs Everywhere**: All analytics use hashed IDs, not raw PII

**Implementation**:

```python
import hashlib
import os

# dbt macros (hash_pii_secure) hash identifiers with HMAC-SHA256 keyed by PII_SALT
# (udfs/pii_hash.py via pii_hash_plugin — matches scripts/anonymize_aeries.py)
# Re-identification lookup encrypts fields with AES-256-GCM + scrypt KDF via PII_ENCRYPTION_KEY
salt = os.environ["PII_SALT"]  # >= 16 random characters
key = os.environ["PII_ENCRYPTION_KEY"]  # >= 32 random characters
```

**Environment Setup**:

```bash
# .env (never commit)
PII_SALT="<32+ char random salt>"
PII_ENCRYPTION_KEY="<64-hex-char random key>"
DATA_RETENTION_YEARS=5
# Break-glass decryption UDF is disabled by default; enable only in audited registrar sessions:
# LFED_ENABLE_PII_DECRYPT=1
```

#### Data Minimization

**Keep sensitive data in Stage 2 only:**

```sql
-- ❌ DO NOT expose raw PII in Stage 3 dashboards
SELECT student_name, email FROM refined.students

-- ✅ Use aggregated data
SELECT grade_level, COUNT(*) FROM refined.students
GROUP BY grade_level
```

**Staging Architecture**:

- **Stage 1**: Raw data with full PII (restricted access)
- **Stage 2**: Pseudonymized analytics views (analyst access)
- **Stage 3**: Aggregated dashboards (educator access)

#### Accepted Deviation: Plaintext Source Identifiers in the Landing Zone and Staging

**Status**: Accepted by design (spec P4-T1 and the fact-layer hashing spec),
reviewed 2026-11-12.

The final `analytics.duckdb` intentionally retains plaintext SOURCE student
IDs and a small, explicitly allowlisted set of identifier columns in exactly
two layers:

1. Stage-1 raw landing objects — the dlt base tables
   (`aeries_stage1.raw_students`, `raw_attendance`, `raw_academic_records`,
   `raw_discipline`, `raw_enrollment`), the `main.raw_*` sync views built
   over them (`SELECT *` by design, so the view set mirrors the base tables
   exactly), and dlt's transient `aeries_stage1_staging` load schema. These
   are required to build the break-glass re-identification lookup
   (`main_privacy_sensitive.priv_pii_lookup_table`, AES-256-GCM ciphertexts):

   - `raw_students`: `student_id`, `first_name`, `last_name`, `date_of_birth`
   - `raw_attendance`, `raw_academic_records`, `raw_discipline`,
     `raw_enrollment`: `student_id` only

2. `main_staging` — the `stg_aeries__*` models retain `student_id_raw` as
   the prescribed lineage/join key (facts derive hashed surrogate keys from
   it via `hash_pii_secure`, per the fact-layer hashing spec); staging holds
   no names, birth dates, or student contact data. `stg_cde__schools`
   additionally carries the school building's own public address columns
   (`street_address`, `city`, `zip_code`) from CDE public downloads —
   institutional metadata, not student PII.

Every other plaintext PII field (phones, addresses, StateStudentID,
OldStudentID, …) is dropped at ingestion by the Stage-1 allowlist
(`STUDENT_STAGE1_ALLOWLIST`). All facts, marts, and
`main_privacy.priv_student_hashes` carry HMAC-SHA256 hashes only — verified
on the 2026-11-12 rebuild (no `student_id`/`student_id_raw` column exists
outside the two layers above). Every query client (desktop validator,
NL→SQL engine) must enforce the schema/column allowlist AND reject staging
or raw tokens (`student_id_raw`, `\w+_raw`, staging model names) per the
spec's query guard; the barrier is procedural by design, not absence of
data. `oss_framework/tests/test_public_release_sanitization.py` audits live
warehouses (`*stage1.raw_*` base tables, `main.raw_*` sync views, and the
`main_staging` lineage-key boundary) against this exact allowlist so new
plaintext columns fail the gate until it is consciously extended.

#### Right to Be Forgotten

**Delete student data:**

```sql
-- Delete all records for a student
DELETE FROM raw_students WHERE student_id = 'hashed_student_id';
DELETE FROM raw_attendance WHERE student_id = 'hashed_student_id';
-- Cascade to all related tables
```

**Automated Retention (`DATA_RETENTION_YEARS`)**:

```python
import duckdb
from oss_framework.scripts.config import purge_expired_records

with duckdb.connect("oss_framework/data/analytics.duckdb") as conn:
    deleted = purge_expired_records(conn)  # honors DATA_RETENTION_YEARS
```

---

### 2. Data Encryption

#### Encryption at Rest

**DuckDB File Encryption**:

DuckDB does not support native encryption. Use filesystem-level encryption:

- **Linux**: Use LUKS/dm-crypt
  ```bash
  cryptsetup luksFormat /dev/sdX
  cryptsetup open /dev/sdX oea_encrypted
  mkfs.ext4 /dev/mapper/oea_encrypted
  mount /dev/mapper/oea_encrypted /data
  ```

- **Windows**: Use BitLocker
  ```powershell
  Enable-BitLocker -MountPoint "D:" -EncryptionMethod Aes256
  ```

- **macOS**: Use FileVault (System Preferences → Security & Privacy)

#### Encryption in Transit

**Rill HTTPS Setup (Required for production):**

```yaml
# Rill configuration (rill.yaml)
security:
  tls:
    enabled: true
    cert_file: /path/to/cert.pem
    key_file: /path/to/key.pem
```

**For development**: Rill runs on localhost (http://localhost:9009) by default. Use SSH tunneling for remote access:

```bash
# From remote machine
ssh -L 9009:localhost:9009 user@your-server

# Access Rill at http://localhost:9009 locally
```

#### Network Security

- **Firewall**: Restrict access to Rill and JupyterLab
  ```bash
  # Example: ufw (Ubuntu)
  sudo ufw allow from 192.168.1.0/24 to any port 9009  # Rill (internal only)
  sudo ufw allow from 192.168.1.0/24 to any port 8888  # JupyterLab (internal only)
  sudo ufw deny 9009  # Block external access
  ```

- **VPN**: Use VPN for remote access to services
- **No Public Exposure**: Never expose DuckDB or JupyterLab to the internet

---

### 3. Authentication & Authorization

#### Rill Access Control

**Authentication Options**:

1. **Local Development** (default): No authentication required (runs on localhost)
2. **Production Deployment**: Use Rill Cloud authentication or configure reverse proxy with auth

**Role-Based Dashboards**:

```yaml
# dashboards/admin_dashboard.yaml
type: metrics_view
model: chronic_absenteeism_risk
# Restrict via reverse proxy (Nginx, Caddy) with auth
```

**Data Governance with SQL**:

```sql
-- Example: Create restricted view for educators
CREATE VIEW educator_dashboard AS
SELECT
    school_id,
    grade_level,
  attendance_rate_30d,
    -- NO student-level PII
FROM main_main_analytics.v_chronic_absenteeism_risk
WHERE school_id IN (SELECT school_id FROM user_access WHERE user_id = current_user());
```

#### System Access

- **SSH Keys Only**: Disable password authentication
  ```bash
  # /etc/ssh/sshd_config
  PasswordAuthentication no
  PubkeyAuthentication yes
  ```

- **Sudo Access**: Limit to essential administrators
- **Service Accounts**: Use dedicated accounts for pipeline execution

---

### 4. DuckDB Security

#### File Permissions

```bash
# Restrict DuckDB file access
chmod 600 data/analytics.duckdb
chown analytics-user:analytics-group data/analytics.duckdb
```

#### Read-Only Access

```python
# For analytics users (read-only)
import duckdb
con = duckdb.connect('data/analytics.duckdb', read_only=True)
```

#### Query Injection Prevention

**Always use parameterized queries:**

```python
# ❌ UNSAFE: SQL injection risk
query = f"SELECT * FROM students WHERE name = '{user_input}'"

# ✅ SAFE: Parameterized query
query = "SELECT * FROM students WHERE name = ?"
con.execute(query, [user_input])
```

#### Connection Pooling

```python
# Limit concurrent connections
con = duckdb.connect('data/analytics.duckdb', config={
    'threads': 4,
    'max_memory': '2GB'
})
```

---

### 5. Pipeline Security

#### dlt Credential Management

**Store credentials securely:**

```bash
# .env (not tracked in Git)
AERIES_API_KEY="your_api_key_here"
AERIES_BASE_URL="https://your-district.aeries.net/api/v5"
```

**Never log secrets:**

```python
import logging
logger = logging.getLogger(__name__)

# ❌ DO NOT log API keys
logger.info(f"API Key: {os.getenv('AERIES_API_KEY')}")

# ✅ Log without secrets
logger.info("Connecting to Aeries API...")
```

#### dbt Security

**Secure profiles.yml:**

```bash
# Restrict dbt profiles
chmod 600 ~/.dbt/profiles.yml

# profiles.yml
local_data_stack:
  outputs:
    dev:
      type: duckdb
      path: ./oss_framework/data/analytics.duckdb
      threads: 4
```

---

### 6. Audit Logging

#### Pipeline Execution Logs

**All pipeline runs are logged:**

```bash
# View recent pipeline logs
tail -f oss_framework/logs/oea.log

# Search for specific errors
grep ERROR oss_framework/logs/oea.log
```

**Retain logs for compliance:**

```python
# logging_config.py
logging.config.dictConfig({
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'oss_framework/logs/oea.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10  # Keep 10 rotated logs
        }
    }
})
```

#### Rill Query Logs

**Monitor dashboard access:**

Rill logs all queries to stdout. Capture with Docker logging:

```yaml
# docker-compose.yml
rill:
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "10"
```

**View Rill logs:**

```bash
docker-compose logs -f rill
```

#### Access Logs

**Monitor access to sensitive files:**

```bash
# Linux: auditd
sudo auditctl -w /path/to/data/stage2/refined/sensitive -p rwa -k sensitive_access

# View logs
sudo ausearch -k sensitive_access
```

---

### 7. Backup & Disaster Recovery

#### Encrypted Backups

```bash
# Example: Encrypted backup to external drive
tar czf - data/ | openssl enc -aes-256-cbc -salt -out backup.tar.gz.enc

# Restore
openssl enc -d -aes-256-cbc -in backup.tar.gz.enc | tar xzf -
```

#### Backup Retention

- **Daily**: Keep 7 days
- **Weekly**: Keep 4 weeks
- **Monthly**: Keep 12 months
- **Annually**: Keep 7 years (FERPA requirement)

#### DuckDB-Specific Backups

```bash
# Backup DuckDB file
cp data/analytics.duckdb backups/oea_$(date +%Y%m%d).duckdb

# Backup Parquet files (Stage 1 source of truth)
rsync -av data/stage1/ backups/stage1_$(date +%Y%m%d)/
```

---

### 8. Secure Configuration

#### Environment Variables

**Never commit secrets to Git:**

```bash
# .env (not tracked in Git)
PII_SALT="<random-salt-min-16-chars>"
PII_ENCRYPTION_KEY="<random-key-min-32-chars>"
AERIES_API_KEY="<aeries-api-cert>"
DATA_RETENTION_YEARS=5
```

**Use `.gitignore`:**

```gitignore
.env
*.key
*.pem
*.p12
data/stage2/refined/sensitive/
oss_framework/data/*.duckdb
```

#### Configuration Validation

```bash
# Check for exposed secrets
git secrets --scan

# Or use gitleaks
gitleaks detect --source . --verbose
```

#### Docker Security

**Don't run as root:**

```yaml
# docker-compose.yml
rill:
  user: "1000:1000"  # Non-root user
  read_only: true
  tmpfs:
    - /tmp
```

**Limit resources:**

```yaml
rill:
  mem_limit: 2g
  cpus: 2
```

---

### 9. Dependency Management

#### Python Dependencies

**Pin versions in requirements.txt:**

```txt
duckdb==1.1.3
dlt[duckdb]==1.5.0
dbt-duckdb==1.9.1
rill-cli==0.81.4
```

**Check for vulnerabilities:**

```bash
pip install safety
safety check --file requirements.txt
```

#### Regular Updates

```bash
# Update dependencies
pip install --upgrade duckdb dlt dbt-duckdb

# Test after updates
pytest oss_framework/tests/
```

#### Known Accepted Vulnerabilities

The following Dependabot alerts have been triaged and accepted as documented
risk. They are not exploitable in the local-data-stack threat model (local-first
tool, no internet-facing server, no untrusted input reaching the vulnerable code
path). They will be resolved when upstream patches are available.

| Package | GHSA | Risk | Rationale |
|---|---|---|---|
| `diskcache` 5.6.3 | GHSA-w8v5-vhqr-4h9v | Unsafe pickle deserialization | Transitive via `llama-cpp-python` (nl-query extra). **No patched version exists.** Requires attacker write access to the local cache directory — equivalent to local box compromise. Local-only tool; accepted until upstream fix. |
| `black` < 26.3.1 | GHSA-3936-cmfr-pm3m | Arbitrary file write via cache filename | Dev-only formatter. Requires attacker-controlled filenames fed to `black`. Cannot bump to 26.3.1 because it requires `pathspec>=1.0.0`, which conflicts with `dbt-core`'s `pathspec<0.13` pin. Will resolve when dbt relaxes the pathspec constraint. |

---

### 10. Compliance & Monitoring

#### FERPA Compliance

- ✅ **Pseudonymization**: All PII hashed
- ✅ **Access Control**: Role-based access via system permissions
- ✅ **Audit Logging**: All pipeline runs logged
- ✅ **Data Retention**: 7-year retention enforced
- ✅ **Right to Be Forgotten**: Student data deletion supported

#### GDPR Compliance (if applicable)

- ✅ **Data Minimization**: Only necessary data collected
- ✅ **Purpose Limitation**: Data used only for education analytics
- ✅ **Storage Limitation**: Automated deletion after 7 years
- ✅ **Integrity & Confidentiality**: Encryption at rest and in transit

#### Monitoring

**System Health:**

```bash
# Check DuckDB file size
du -sh data/analytics.duckdb

# Check disk space
df -h

# Check pipeline logs for errors
grep ERROR oss_framework/logs/oea.log | tail -20
```

**Performance Monitoring:**

```sql
-- DuckDB-compatible row count check for active tables
SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'main'
ORDER BY table_name;
```

---

## Security Checklist

Use this checklist before production deployment:

- [ ] Pseudonymization configured with unique salt
- [ ] Filesystem encryption enabled (LUKS/BitLocker/FileVault)
- [ ] Rill HTTPS enabled (production only)
- [ ] Firewall rules configured (block external access)
- [ ] SSH key authentication enabled, passwords disabled
- [ ] DuckDB file permissions restricted (chmod 600)
- [ ] `.env` file excluded from Git (in `.gitignore`)
- [ ] All API credentials stored in `.env`
- [ ] Pipeline logs rotating (10MB max, 10 files)
- [ ] Rill query logs captured (Docker logging)
- [ ] Encrypted backups configured (daily/weekly/monthly)
- [ ] Backup retention policy enforced (7-year FERPA)
- [ ] Python dependencies pinned in requirements.txt
- [ ] Vulnerability scan passed (`safety check`)
- [ ] System access limited to authorized users only
- [ ] Data retention policy documented and enforced

---

## Security Resources

- **FERPA Compliance**: https://www2.ed.gov/policy/gen/guid/fpco/ferpa/index.html
- **GDPR Overview**: https://gdpr.eu/
- **DuckDB Security**: https://duckdb.org/docs/security
- **Rill Security**: https://docs.rilldata.com/deploy/security
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.0 | 2026-02-24 | Removed Metabase, added Rill security guidance |
| 2.0 | 2026-01-27 | Updated for MotherDuck removal, local-only architecture |
| 1.0 | 2026-01-20 | Initial security policy |

---

## Contact

For security concerns or questions:

- **GitHub Issues**: https://github.com/flucido/local-data-stack/issues (non-sensitive only)
- **Security Email**: frank@flucido.com
- **Private Advisory**: https://github.com/flucido/local-data-stack/security/advisories/new
