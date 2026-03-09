{{ config(materialized='table') }}

WITH watchlist AS (
    SELECT * FROM {{ source('raw_data', 'cfg_watchlist') }}
),

final_dimension AS (
    SELECT
        symbol AS coin_symbol, -- A nossa Primary Key natural
        name AS coin_name,
        is_active,             -- O tal semáforo para o Power BI filtrar!
        last_updated AS dim_last_updated
    FROM watchlist
)

SELECT * FROM final_dimension