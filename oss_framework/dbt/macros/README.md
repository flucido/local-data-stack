# Privacy & Pseudonymization Macros

## Overview

This directory contains dbt macros for pseudonymization, PII masking, and k-anonymity validation. These macros enforce FERPA compliance and protect student privacy across all analytics models.

## Macro Catalog

### Hashing Macros

#### `hash_pii_secure(column_name)`

**Purpose**: Secure one-way hashing using SHA256 for pseudonymization.

**Algorithm**: SHA256 (cryptographically secure, 256-bit output)

**Output**: 64-character hexadecimal string

**Usage**:
```sql
SELECT
    {{ hash_pii_secure('student_id_raw') }} as student_id_hash
FROM {{ ref('stg_aeries__students') }}
```

**Implementation**:
```sql
{% macro hash_pii_secure(column_name) %}
    sha256(CONCAT('your_salt_here', {{ column_name }}))
{% endmacro %}
```

**Security Notes**:
- ⚠️ **Replace placeholder salt** with a secure, randomly-generated value in production
- ✅ Deterministic (same input = same hash, enables joins)
- ✅ One-way (cannot reverse hash to original value)
- ✅ Collision-resistant
- ✅ Industry standard for pseudonymization

**Salt Management**:
```sql
-- Recommended: Use environment variable for salt
sha256(CONCAT('{{ env_var("PSEUDONYMIZATION_SALT") }}', {{ column_name }}))

-- Generate salt (outside dbt):
openssl rand -hex 32
```

---

#### `hash_pii(column_name)` *(Deprecated)*

**Purpose**: Legacy MD5 hashing for backwards compatibility.

**⚠️ WARNING**: MD5 is cryptographically broken. Use `hash_pii_secure()` for new implementations.

**Algorithm**: MD5 (128-bit output)

**Output**: 32-character hexadecimal string

**Usage**:
```sql
-- Legacy code only - migrate to hash_pii_secure()
SELECT
    {{ hash_pii('student_id_raw') }} as student_id_hash
FROM {{ ref('stg_aeries__students') }}
```

**Migration Path**:
1. Update SQL to use `hash_pii_secure()` instead of `hash_pii()`
2. Rebuild models with `dbt run --full-refresh`
3. Update downstream joins (hashes will change from MD5 to SHA256)

---

### Masking Macros

#### `mask_name(column_name, num_visible)`

**Purpose**: Irreversible name masking for display purposes.

**Parameters**:
- `column_name` (required): Column containing name to mask
- `num_visible` (optional): Number of characters to preserve (default: 1)

**Behavior**:
- Preserves first N characters
- Replaces remaining characters with asterisks (`*`)
- Handles NULL values (returns NULL)
- Minimum length preserved: 1 character

**Usage**:
```sql
SELECT
    {{ mask_name('first_name_raw', 1) }} as first_name_masked,
    {{ mask_name('last_name_raw', 1) }} as last_name_masked
FROM {{ ref('stg_aeries__students') }}
```

**Examples**:
| Input | num_visible | Output |
|-------|-------------|--------|
| "Johnson" | 1 | "J******" |
| "María" | 1 | "M****" |
| "Smith" | 2 | "Sm***" |
| "Li" | 1 | "L*" |
| NULL | 1 | NULL |

**Implementation**:
```sql
{% macro mask_name(column_name, num_visible=1) %}
    CASE
        WHEN {{ column_name }} IS NULL THEN NULL
        WHEN LENGTH({{ column_name }}) <= {{ num_visible }} THEN {{ column_name }}
        ELSE CONCAT(
            LEFT({{ column_name }}, {{ num_visible }}),
            REPEAT('*', LENGTH({{ column_name }}) - {{ num_visible }})
        )
    END
{% endmacro %}
```

**Use Cases**:
- Display masked names in dashboards
- Show partial names in reports
- Protect student identity while maintaining context

---

#### `mask_email(email_column)`

**Purpose**: Mask email addresses while preserving format.

**Behavior**:
- Masks username (keeps first 2 characters)
- Masks domain (keeps first 2 characters)
- Preserves @ symbol and domain extension
- Handles NULL values (returns NULL)

**Usage**:
```sql
SELECT
    {{ mask_email('email_address') }} as email_masked
FROM {{ ref('stg_aeries__students') }}
```

**Examples**:
| Input | Output |
|-------|--------|
| "john.doe@school.edu" | "jo****@sc****" |
| "admin@district.org" | "ad****@di****" |
| "a@b.com" | "a*@b*" |
| NULL | NULL |

**Implementation**:
```sql
{% macro mask_email(email_column) %}
    CASE
        WHEN {{ email_column }} IS NULL THEN NULL
        WHEN POSITION('@' IN {{ email_column }}) = 0 THEN '***INVALID***'
        ELSE CONCAT(
            LEFT(SPLIT_PART({{ email_column }}, '@', 1), 2),
            '****@',
            LEFT(SPLIT_PART({{ email_column }}, '@', 2), 2),
            '****'
        )
    END
{% endmacro %}
```

**Note**: Current staging data does not contain email fields. This macro is ready for future use.

---

#### `mask_phone(phone_column)`

**Purpose**: Mask phone numbers while preserving area code.

**Behavior**:
- Masks last 4 digits
- Preserves area code and exchange
- Handles various formats (dashes, parentheses, spaces)
- Handles NULL values (returns NULL)

**Usage**:
```sql
SELECT
    {{ mask_phone('phone_number') }} as phone_masked
FROM {{ ref('stg_aeries__students') }}
```

**Examples**:
| Input | Output |
|-------|--------|
| "555-123-4567" | "555-12****" |
| "(555) 123-4567" | "(555) 12****" |
| "5551234567" | "555123****" |
| NULL | NULL |

**Implementation**:
```sql
{% macro mask_phone(phone_column) %}
    CASE
        WHEN {{ phone_column }} IS NULL THEN NULL
        WHEN LENGTH(REGEXP_REPLACE({{ phone_column }}, '[^0-9]', '')) < 4 THEN '***INVALID***'
        ELSE CONCAT(
            LEFT({{ phone_column }}, LENGTH({{ phone_column }}) - 4),
            '****'
        )
    END
{% endmacro %}
```

**Note**: Current staging data does not contain phone fields. This macro is ready for future use.

---

#### `mask_address(address_column)`

**Purpose**: Complete address redaction (highly identifying PII).

**Behavior**:
- Replaces entire address with "***REDACTED***"
- No partial masking (addresses are too identifying)
- Handles NULL values (returns NULL)

**Usage**:
```sql
SELECT
    {{ mask_address('home_address') }} as address_masked
FROM {{ ref('stg_aeries__students') }}
```

**Examples**:
| Input | Output |
|-------|--------|
| "123 Main Street, Apt 4B" | "***REDACTED***" |
| "P.O. Box 456" | "***REDACTED***" |
| NULL | NULL |

**Implementation**:
```sql
{% macro mask_address(address_column) %}
    CASE
        WHEN {{ address_column }} IS NULL THEN NULL
        ELSE '***REDACTED***'
    END
{% endmacro %}
```

**Rationale**: Street addresses are highly identifying. Even partial masking (e.g., "123 Main ****") could enable re-identification in small districts.

**Note**: Current staging data does not contain address fields. This macro is ready for future use.

---

### Validation Macros

#### `check_k_anonymity(quasi_identifiers, k)`

**Purpose**: Helper macro to validate k-anonymity in aggregated data.

**Parameters**:
- `quasi_identifiers` (required): List of column names that form quasi-identifiers
- `k` (required): Minimum group size (FERPA requires k≥5)

**Usage**:
```sql
-- In aggregated model SQL
SELECT
    grade_level,
    gender,
    ethnicity,
    COUNT(DISTINCT student_id_hash) as student_count
FROM {{ ref('priv_student_hashes') }}
GROUP BY grade_level, gender, ethnicity
HAVING {{ check_k_anonymity(['grade_level', 'gender', 'ethnicity'], 5) }}
```

**Implementation**:
```sql
{% macro check_k_anonymity(quasi_identifiers, k=5) %}
    COUNT(DISTINCT student_id_hash) >= {{ k }}
{% endmacro %}
```

**Expands to**:
```sql
COUNT(DISTINCT student_id_hash) >= 5
```

**Note**: This is a helper macro for readability. You can also write the `HAVING` clause directly.

---

## Generic Tests

### `test_k_anonymity`

**Purpose**: dbt generic test to validate k-anonymity on unaggregated data.

**Location**: `tests/generic/test_k_anonymity.sql`

**Usage in YAML**:
```yaml
# ⚠️ ONLY use on unaggregated (student-level) data
# DO NOT use on pre-aggregated models
models:
  - name: fact_attendance
    data_tests:
      - k_anonymity:
          arguments:
            quasi_identifiers: ['attendance_date', 'school_id', 'grade_level']
            k: 5
```

**What It Checks**:
- Counts students in each quasi-identifier combination
- Fails if any group has < k students
- Returns list of violating groups

**⚠️ Important Limitations**:
- **Do NOT use on aggregated models** (e.g., `dim_student_demographics`, `fact_attendance_daily`)
- Test counts ROWS, not `student_count` column
- For aggregated models, rely on `HAVING` clause in SQL instead

**Example Failure Output**:
```
Got 3 results, configured to fail if != 0

grade_level | gender | ethnicity | school_id | group_size | deficit
------------|--------|-----------|-----------|------------|--------
9           | F      | Hispanic  | SCH003    | 3          | 2
11          | M      | Asian     | SCH001    | 4          | 1
12          | X      | Pacific   | SCH002    | 2          | 3
```

**Implementation**: See `tests/generic/test_k_anonymity.sql`

---

## Best Practices

### When to Use Each Macro

| Scenario | Use |
|----------|-----|
| Pseudonymization for joins | `hash_pii_secure()` |
| Legacy pseudonymization | `hash_pii()` (migrate to secure version) |
| Display names in UI | `mask_name()` |
| Display email in UI | `mask_email()` |
| Display phone in UI | `mask_phone()` |
| Display address in UI | `mask_address()` |
| Validate k-anonymity (SQL) | `check_k_anonymity()` helper |
| Validate k-anonymity (test) | `k_anonymity` generic test |

### Security Checklist

Before deploying to production:

- [ ] Replace placeholder salt in `hash_pii_secure()` with secure random value
- [ ] Store salt in environment variable or secrets manager (NOT in code)
- [ ] Verify all fact tables use `hash_pii_secure()` (not `hash_pii()`)
- [ ] Test that masked PII cannot be reversed to original values
- [ ] Verify k-anonymity enforcement in all aggregated models
- [ ] Run full test suite: `dbt test`

### Performance Considerations

**Hashing**:
- SHA256 is computationally expensive for large datasets
- Consider materializing models as tables (not views)
- Index on hashed columns for join performance

**Masking**:
- Masking functions add minimal overhead
- Safe to use in views and CTEs
- No indexing needed (display-only fields)

## Testing

**Run All Privacy Tests**:
```bash
dbt test --select tag:privacy
dbt test --select tag:pseudonymization
```

**Test Specific Model**:
```bash
dbt test --select priv_student_hashes
```

**Test Hashing Consistency**:
```sql
-- Verify same input produces same hash
SELECT
    student_id_raw,
    {{ hash_pii_secure('student_id_raw') }} as hash1,
    {{ hash_pii_secure('student_id_raw') }} as hash2
FROM {{ ref('stg_aeries__students') }}
WHERE hash1 != hash2  -- Should return 0 rows
```

## Related Documentation

- [Privacy Layer README](../models/mart_privacy/README.md) - How macros are used in privacy models
- [Core Marts README](../models/mart_core/README.md) - How hashing is used in fact tables
- [Stage 2B Design Document](../docs/STAGE2B_PRIVACY_DESIGN.md) - Privacy layer design

## Metrics

**Current State**:
- ✅ 6 privacy macros (2 hashing + 4 masking)
- ✅ 1 k-anonymity helper macro
- ✅ 1 generic test (k_anonymity)
- ✅ SHA256 implementation (DuckDB-native)
- ✅ All macros tested and working

**Last Updated**: 2026-01-28
