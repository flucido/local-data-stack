
-- models/mart_privacy/privacy/priv_pii_lookup_table.sql
-- SENSITIVE: PII Lookup Table (AES-256-GCM encrypted at rest)
-- Maps hashes back to identifiable information.
--
-- All plaintext PII fields are wrapped with the aes_encrypt_pii() Python UDF
-- (AES-256-GCM, authenticated encryption; key from PII_ENCRYPTION_KEY env
-- var, registered via profiles.yml `udfs:`). Decryption is only possible
-- with aes_decrypt_pii() in a session that holds the key. Store in a
-- separate restricted schema.

{{ config(
    materialized='table',
    schema='privacy_sensitive',
    unique_key='student_id_hash',
    tags=['privacy', 'sensitive_pii']
) }}

SELECT
    -- Hashed ID (key for linking)
    {{ hash_pii('student_id_raw') }} as student_id_hash,

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
