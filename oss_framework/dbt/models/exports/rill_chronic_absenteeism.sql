{% set rill_export_dir = env_var('RILL_EXPORT_DIR', '../../rill_project/data') %}
{{
  config(
    materialized='external',
    location=rill_export_dir ~ '/chronic_absenteeism_risk.parquet',
    format='parquet',
    tags=['rill_export']
  )
}}

SELECT * FROM {{ ref('v_chronic_absenteeism_risk') }}
