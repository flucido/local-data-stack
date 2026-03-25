
-- models/mart_privacy/privacy/priv_pii_lookup_table.sql
-- SENSITIVE: PII Lookup Table (Encryption at Rest Required)
-- Maps hashes back to identifiable information
-- Store in separate encrypted schema

{{ config(
    materialized='table',
    schema='privacy_sensitive',
    unique_key='student_id_hash',
    tags=['privacy', 'sensitive_pii']
) }}

SELECT
    -- Hashed ID (key for linking)
    {{ hash_pii('student_id_raw') }} as student_id_hash,
    
    -- Original identifiable data (REQUIRES ENCRYPTION)
    student_id_raw,
    first_name_raw,
    last_name_raw,
    date_of_birth_raw,
    academic_year,
    
    -- Access control fields
    'RESTRICTED' as access_level,
    CURRENT_TIMESTAMP as created_at,
    NULL as accessed_by,
    0 as access_count,
    
    -- Audit
    'ENCRYPTED_STORAGE_REQUIRED' as storage_note

FROM {{ ref('stg_aeries__students') }}

