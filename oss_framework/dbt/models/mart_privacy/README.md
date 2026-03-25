# Privacy Layer (mart_privacy)

## Overview

The privacy layer provides pseudonymization and PII masking capabilities to ensure FERPA compliance and protect student privacy. This layer transforms raw personally identifiable information (PII) into secure, pseudonymous identifiers that enable analytics while preventing re-identification.

## Purpose

The privacy layer serves as the bridge between raw source data and analytics marts. It provides:

- **Pseudonymization**: One-way hashing of identifiers using SHA256
- **PII Masking**: Irreversible obfuscation of names, emails, addresses
- **Secure Lookup**: Restricted-access table for re-identification when legally required
- **FERPA Compliance**: Ensures educational records meet federal privacy standards

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Staging Layer                           │
│              (stg_aeries__students, etc.)                   │
│                  Contains Raw PII                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Privacy Layer                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  priv_student_hashes (schema: main_privacy)          │  │
│  │  - Pseudonymized identifiers (SHA256)                │  │
│  │  - Masked PII (first_name_masked, last_name_masked)  │  │
│  │  - Non-PII demographics                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  priv_pii_lookup_table (schema: main_privacy_        │  │
│  │                        sensitive)                     │  │
│  │  ⚠️  RESTRICTED ACCESS - Contains Raw PII             │  │
│  │  - Used only for legally-mandated re-identification  │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 Core Analytics Marts                        │
│  - dim_students, fact_attendance, etc.                      │
│  - Join on student_id_hash (no raw PII)                    │
└─────────────────────────────────────────────────────────────┘
```

## Models

### `priv_student_hashes`

Pseudonymized student identifiers with masked PII for privacy-preserving analytics.

**Schema**: `main_privacy`  
**Materialization**: Table  
**Grain**: One row per student

**Key Columns**:
- `student_id_hash` (VARCHAR) - SHA256 hash of student_id_raw (64 characters)
- `first_name_masked` (VARCHAR) - Masked first name ("Johnson" → "J******")
- `last_name_masked` (VARCHAR) - Masked last name  
- `age_at_event` (INTEGER) - Age in years (NOT date of birth - better privacy)
- Demographics fields (gender, ethnicity, grade_level, school_id, etc.)

**Privacy Features**:
- ✅ SHA256 hashing (cryptographically secure, one-way)
- ✅ Name masking (irreversible, display-only)
- ✅ Age instead of DOB (reduces re-identification risk)
- ✅ No raw PII exposed

**Use Cases**:
- Join key for all core analytics models
- Display masked names in dashboards
- Age-based cohort analysis

**Example Query**:
```sql
SELECT
    student_id_hash,
    first_name_masked || ' ' || last_name_masked as masked_full_name,
    grade_level,
    age_at_event
FROM {{ ref('priv_student_hashes') }}
WHERE school_id = 'SCH001'
```

---

### `priv_pii_lookup_table`

Secure lookup table mapping hashed identifiers back to raw PII.

**Schema**: `main_privacy_sensitive` (restricted access)  
**Materialization**: Table  
**Grain**: One row per student

**⚠️ CRITICAL SECURITY NOTICE**:
- This table contains raw PII and MUST be restricted to authorized personnel only
- Access should be limited to: Registrar, Compliance Officers, Legal team
- Should NEVER be joined to analytics models
- Use ONLY for legally-mandated re-identification requests

**Key Columns**:
- `student_id_hash` (VARCHAR) - SHA256 hash (join key to pseudonymized models)
- `student_id_raw` (VARCHAR) - ⚠️ SENSITIVE: Raw student identifier
- `first_name_raw` (VARCHAR) - ⚠️ SENSITIVE: Student first name
- `last_name_raw` (VARCHAR) - ⚠️ SENSITIVE: Student last name
- `date_of_birth_raw` (DATE) - ⚠️ SENSITIVE: Student date of birth

**Legal Use Cases**:
- FERPA-mandated parent requests for student records
- Compliance audits requiring identity verification
- Legal discovery requests
- Incident response (e.g., disciplinary appeals)

**Access Control**:
```sql
-- Example: Grant restricted access
GRANT SELECT ON main_privacy_sensitive.priv_pii_lookup_table 
TO ROLE registrar;

GRANT SELECT ON main_privacy_sensitive.priv_pii_lookup_table 
TO ROLE compliance_officer;

-- Deny access to analysts
REVOKE SELECT ON main_privacy_sensitive.priv_pii_lookup_table 
FROM ROLE analyst;
```

**Example Query** (authorized personnel only):
```sql
-- Re-identify a specific student for a parent FERPA request
SELECT
    p.student_id_raw,
    p.first_name_raw,
    p.last_name_raw,
    p.date_of_birth_raw
FROM {{ ref('priv_pii_lookup_table') }} p
WHERE p.student_id_hash = '<hash_from_analytics_query>';
```

## Hashing Methodology

### SHA256 (Current Standard)

The privacy layer uses SHA256 hashing via the `hash_pii_secure()` macro.

**Properties**:
- ✅ Cryptographically secure (256-bit output)
- ✅ One-way function (cannot reverse hash to original value)
- ✅ Deterministic (same input = same output, enables joins)
- ✅ Collision-resistant (extremely low probability of duplicates)
- ✅ Industry standard for pseudonymization

**Implementation**:
```sql
-- Macro definition: macros/hash_pii_secure.sql
{{ hash_pii_secure('student_id_raw') }}

-- Expands to:
sha256(CONCAT('your_salt_here', student_id_raw))
```

**Output**: 64-character hexadecimal string (e.g., `a3f2c1...`)

### MD5 (Legacy - Deprecated)

The older `hash_pii()` macro uses MD5 hashing.

**⚠️ WARNING**: MD5 is considered cryptographically broken and should NOT be used for new implementations.

**Issues with MD5**:
- ❌ Vulnerable to collision attacks
- ❌ Can be brute-forced with rainbow tables
- ❌ Not recommended for security-sensitive applications

**Migration Path**:
- New models: Use `hash_pii_secure()` (SHA256)
- Existing models: Migrate to SHA256 when rebuilding
- Legacy models: Continue using `hash_pii()` for backwards compatibility

## Masking Patterns

The privacy layer provides irreversible masking for display purposes.

### Name Masking

**Macro**: `mask_name(column_name, num_visible)`

**Behavior**:
- Preserves first N characters (default: 1)
- Replaces remaining characters with asterisks (`*`)
- Handles NULL values gracefully

**Examples**:
```sql
{{ mask_name('first_name_raw', 1) }}
-- "Johnson" → "J******"
-- "María" → "M****"
-- NULL → NULL

{{ mask_name('last_name_raw', 2) }}
-- "Smith" → "Sm***"
```

**Use Cases**:
- Display masked names in dashboards
- Show partial names in reports
- Protect student identity while maintaining context

### Email Masking

**Macro**: `mask_email(email_column)`

**Behavior**:
- Masks username (keeps first 2 chars)
- Masks domain (keeps first 2 chars)
- Preserves @ symbol

**Examples**:
```sql
{{ mask_email('email_address') }}
-- "john.doe@school.edu" → "jo****@sc****"
-- "admin@district.org" → "ad****@di****"
-- NULL → NULL
```

**Note**: Current staging data does not contain email fields. This macro is ready for future use.

### Phone Number Masking

**Macro**: `mask_phone(phone_column)`

**Behavior**:
- Masks last 4 digits
- Preserves area code and exchange
- Handles various formats

**Examples**:
```sql
{{ mask_phone('phone_number') }}
-- "555-123-4567" → "555-12****"
-- "(555) 123-4567" → "(555) 12****"
-- NULL → NULL
```

**Note**: Current staging data does not contain phone fields. This macro is ready for future use.

### Address Masking

**Macro**: `mask_address(address_column)`

**Behavior**:
- Complete redaction (replaces entire address with "***REDACTED***")
- Addresses are highly identifying - no partial masking

**Examples**:
```sql
{{ mask_address('home_address') }}
-- "123 Main Street, Apt 4B" → "***REDACTED***"
-- NULL → NULL
```

**Note**: Current staging data does not contain address fields. This macro is ready for future use.

## K-Anonymity Enforcement

K-anonymity ensures that every individual in a dataset is indistinguishable from at least k-1 other individuals based on quasi-identifiers.

**FERPA Requirement**: Educational data aggregations must use k≥5 to prevent re-identification.

**Quasi-Identifiers**: Combinations of attributes that could identify individuals:
- Grade level + Gender + Ethnicity + School
- Date + School + Grade level
- Demographics + Program participation flags

**Implementation**: K-anonymity is enforced in aggregated models (not in this layer):
- `dim_student_demographics` - Uses `HAVING COUNT(DISTINCT student_id_hash) >= 5`
- `fact_attendance_daily` - Uses `HAVING COUNT(DISTINCT student_id_hash) >= 5`

See [Core Marts README](../mart_core/README.md) for details on aggregated models.

## FERPA Compliance

The Family Educational Rights and Privacy Act (FERPA) protects student education records.

**Key Requirements**:
1. **PII Protection**: Personally identifiable information must be protected
2. **Minimum Suppression**: Aggregated data must have ≥5 students per group
3. **Re-identification Risk**: Data must not allow identification of individuals
4. **Access Controls**: PII lookup tables must be restricted

**How This Layer Achieves Compliance**:
- ✅ Pseudonymization via SHA256 hashing (one-way, irreversible)
- ✅ PII masking for display purposes
- ✅ Separation of pseudonymized analytics from raw PII
- ✅ Restricted-access lookup table for authorized re-identification
- ✅ K-anonymity enforcement in aggregated models (see Core Marts)

**Non-Compliance Risks**:
- ❌ Exposing raw PII in analytics tables
- ❌ Allowing analysts access to `priv_pii_lookup_table`
- ❌ Creating aggregations with <5 students per group
- ❌ Combining quasi-identifiers that enable re-identification

## Security Considerations

### Salt Management

**Current State**: The `hash_pii_secure()` macro uses a placeholder salt.

**⚠️ PRODUCTION REQUIREMENT**: Replace placeholder with a secure, randomly-generated salt.

**Best Practices**:
- Generate salt using cryptographically secure random generator
- Store salt in environment variable or secrets manager (NOT in code)
- Use same salt consistently across all hashing operations
- Rotate salt only when re-identifying all records (requires full rebuild)

**Implementation**:
```sql
-- macros/hash_pii_secure.sql
{% macro hash_pii_secure(column_name) %}
    sha256(CONCAT('{{ env_var("PSEUDONYMIZATION_SALT") }}', {{ column_name }}))
{% endmacro %}
```

### Access Control

**Recommended Permissions**:

| Role | `priv_student_hashes` | `priv_pii_lookup_table` |
|------|----------------------|------------------------|
| Analyst | SELECT | DENY |
| Dashboard User | SELECT | DENY |
| Registrar | SELECT | SELECT |
| Compliance Officer | SELECT | SELECT |
| System Admin | SELECT | SELECT |

### Audit Logging

**Recommendation**: Log all access to `priv_pii_lookup_table`:
- Who accessed the table
- When
- What records were queried
- Purpose/justification

## Data Quality

**Tests Implemented**:
- ✅ Uniqueness of `student_id_hash` in both models
- ✅ Not-null constraints on hashed identifiers
- ✅ Not-null constraints on masked PII fields
- ✅ Relationship integrity between privacy and core layers

**Test Coverage**: 14 tests across 2 models

**Run Tests**:
```bash
dbt test --select mart_privacy
```

## Maintenance

### Adding New PII Fields

When adding new PII fields (e.g., email, phone):

1. **Add to staging layer** with `_raw` suffix
2. **Update `priv_student_hashes`** to include masked version
3. **Update `priv_pii_lookup_table`** to include raw version
4. **Add tests** for uniqueness and not-null constraints
5. **Update access controls** for new sensitive fields

### Migrating from MD5 to SHA256

To migrate existing models:

1. **Backup data** before making changes
2. **Update SQL** to use `hash_pii_secure()` instead of `hash_pii()`
3. **Rebuild models** with `dbt run --full-refresh --select <model>`
4. **Update downstream joins** (hashes will change)
5. **Test thoroughly** before deploying to production

### Performance Considerations

**Hashing Performance**:
- SHA256 is computationally more expensive than MD5
- For large datasets (>1M records), consider materializing as table
- Indexing on `student_id_hash` improves join performance

**Current Materialization**: `priv_student_hashes` is materialized as `table` for optimal performance.

## Related Documentation

- [Core Marts README](../mart_core/README.md) - K-anonymity enforcement in aggregated models
- [Macros README](../../macros/README.md) - Detailed documentation of hashing and masking macros
- [Staging Layer README](../staging/aeries/README.md) - Raw PII fields in source data
- [Stage 2B Design Document](../../../docs/STAGE2B_PRIVACY_DESIGN.md) - Privacy layer design and requirements

## Metrics

**Current State**:
- ✅ 2 privacy models
- ✅ 6 masking/hashing macros
- ✅ 14 data tests (100% passing)
- ✅ SHA256 hashing implemented
- ✅ FERPA-compliant design
- ✅ Restricted-access lookup table

**Last Updated**: 2026-01-28
