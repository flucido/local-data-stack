-- models/mart_privacy/privacy/priv_pii_lookup_table.sql
-- SENSITIVE: PII Lookup Table (AES-256-GCM encrypted at rest)
-- depends_on: {{ ref('priv_student_hashes') }}

{{ config(
    materialized='table',
    schema='privacy_sensitive',
    unique_key=['student_id_hash', 'academic_year'],
    tags=['privacy', 'sensitive_pii'],
    post_hook=[
        "ALTER TABLE {{ ref('stg_aeries__students') }} DROP COLUMN IF EXISTS first_name_raw",
        "ALTER TABLE {{ ref('stg_aeries__students') }} DROP COLUMN IF EXISTS last_name_raw",
        "ALTER TABLE {{ ref('stg_aeries__students') }} DROP COLUMN IF EXISTS date_of_birth_raw"
    ]
) }}

SELECT
    -- Hashed ID (key for linking)
    {{ hash_pii_secure('student_id_raw') }} as student_id_hash,

    -- Identifiable data, encrypted at rest with AES-256-GCM
    aes_encrypt_pii(student_id_raw::VARCHAR) as student_id_enc,
    aes_encrypt_pii(first_name_raw::VARCHAR) as first_name_enc,
    aes_encrypt_pii(last_name_raw::VARCHAR) as last_name_enc,
    aes_encrypt_pii(date_of_birth_raw::VARCHAR) as date_of_birth_enc,
    academic_year,

    -- Access control fields
    'RESTRICTED' as access_level,
    CURRENT_TIMESTAMP as created_at,
    NULL as accessed_by,
    0 as access_count,

    -- Audit
    'AES_256_GCM_ENCRYPTED' as storage_note

FROM {{ ref('stg_aeries__students') }}
