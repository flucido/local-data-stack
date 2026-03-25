{% set rill_export_dir = env_var('RILL_EXPORT_DIR', '../../rill_project/data') %}
{{
  config(
    materialized='external',
    location=rill_export_dir ~ '/equity_outcomes_by_demographics.parquet',
    format='parquet',
    tags=['rill_export']
  )
}}

SELECT * FROM {{ ref('v_equity_outcomes_by_demographics') }}
