{{ config(
    materialized='view',
    schema='staging'
) }}

WITH source AS (
    SELECT * FROM read_csv(
        '{{ env_var("CDE_PUBLIC_SCHOOLS_PATH", "../data/raw/public_schools/pubschls.txt") }}',
        delim = '\t',
        header = true,
        auto_detect = false,
        columns = {
            'CDSCode': 'VARCHAR',
            'NCESDist': 'VARCHAR',
            'NCESSchool': 'VARCHAR',
            'StatusType': 'VARCHAR',
            'County': 'VARCHAR',
            'District': 'VARCHAR',
            'School': 'VARCHAR',
            'Street': 'VARCHAR',
            'StreetAbr': 'VARCHAR',
            'City': 'VARCHAR',
            'Zip': 'VARCHAR',
            'State': 'VARCHAR',
            'MailStreet': 'VARCHAR',
            'MailStrAbr': 'VARCHAR',
            'MailCity': 'VARCHAR',
            'MailZip': 'VARCHAR',
            'MailState': 'VARCHAR',
            'Phone': 'VARCHAR',
            'Ext': 'VARCHAR',
            'FaxNumber': 'VARCHAR',
            'WebSite': 'VARCHAR',
            'OpenDate': 'VARCHAR',
            'ClosedDate': 'VARCHAR',
            'Charter': 'VARCHAR',
            'CharterNum': 'VARCHAR',
            'FundingType': 'VARCHAR',
            'DOC': 'VARCHAR',
            'DOCType': 'VARCHAR',
            'SOC': 'VARCHAR',
            'SOCType': 'VARCHAR',
            'EdOpsCode': 'VARCHAR',
            'EdOpsName': 'VARCHAR',
            'EILCode': 'VARCHAR',
            'EILName': 'VARCHAR',
            'GSoffered': 'VARCHAR',
            'GSserved': 'VARCHAR',
            'Virtual': 'VARCHAR',
            'Magnet': 'VARCHAR',
            'YearRoundYN': 'VARCHAR',
            'FederalDFCDistrictID': 'VARCHAR',
            'Latitude': 'DOUBLE',
            'Longitude': 'DOUBLE',
            'AdmFName': 'VARCHAR',
            'AdmLName': 'VARCHAR',
            'LastUpDate': 'VARCHAR',
            'Multilingual': 'VARCHAR'
        },
        nullstr = 'No Data',
        ignore_errors = false
    )
),

renamed AS (
    SELECT
        CDSCode AS cds_code,
        NCESDist AS nces_district_id,
        NCESSchool AS nces_school_id,
        StatusType AS status_type,
        County AS county_name,
        District AS district_name,
        School AS school_name,
        Street AS street_address,
        City AS city,
        Zip AS zip_code,
        State AS state_code,
        Phone AS phone_number,
        WebSite AS website_url,
        CASE 
            WHEN OpenDate = 'No Data' OR OpenDate IS NULL THEN NULL
            ELSE TRY_CAST(OpenDate AS DATE)
        END AS open_date,
        CASE 
            WHEN ClosedDate = 'No Data' OR ClosedDate IS NULL THEN NULL
            ELSE TRY_CAST(ClosedDate AS DATE)
        END AS closed_date,
        Charter AS is_charter,
        CharterNum AS charter_number,
        DOC AS doc_code,
        DOCType AS doc_type,
        SOC AS soc_code,
        SOCType AS soc_type,
        EdOpsCode AS ed_ops_code,
        EdOpsName AS ed_ops_name,
        EILCode AS eil_code,
        EILName AS eil_name,
        GSoffered AS grades_offered,
        GSserved AS grades_served,
        Virtual AS is_virtual,
        Magnet AS is_magnet,
        Latitude AS latitude,
        Longitude AS longitude,
        AdmFName AS admin_first_name,
        AdmLName AS admin_last_name,
        CASE 
            WHEN LastUpDate = 'No Data' OR LastUpDate IS NULL THEN NULL
            ELSE TRY_CAST(LastUpDate AS DATE)
        END AS last_updated_date,
        CURRENT_TIMESTAMP AS dbt_loaded_at
    FROM source
    WHERE StatusType = 'Active'
)

SELECT * FROM renamed
