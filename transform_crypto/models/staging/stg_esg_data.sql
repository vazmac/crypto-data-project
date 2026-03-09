WITH source AS (
    SELECT * FROM {{ source('raw_data', 'esg_data') }}
),

silver_esg AS (
    SELECT
        -- IDs e Metadados
        id AS raw_esg_id,
        symbol,
        (esg_data->>'name')::varchar AS coin_name,
        ingested_at,
        -- Limpeza do -1.0 para NULL
        NULLIF((esg_data->>'electrical_power_kw')::numeric, -1.0) AS electrical_power_kw,
        NULLIF((esg_data->>'electricity_consumption_kwh')::numeric, -1.0) AS electricity_consumption_kwh,
        NULLIF((esg_data->>'co2_emissions_kg')::numeric, -1.0) AS co2_emissions_kg
        
    FROM source
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY symbol, DATE(ingested_at) ORDER BY ingested_at DESC) AS rn
    FROM silver_esg
)

SELECT 
    raw_esg_id,
    symbol,
    coin_name,
    ingested_at,
    electrical_power_kw,
    electricity_consumption_kwh,
    co2_emissions_kg
FROM deduped
WHERE rn = 1