WITH source AS (
    SELECT * FROM {{ source('coingecko', 'market_data') }}
),

flattened AS (
    SELECT
        coin_id,
        vs_currency,
        ingested_at,
        CAST(coin_data ->> 'current_price' AS NUMERIC) AS current_price,
        CAST(coin_data ->> 'market_cap' AS NUMERIC) AS market_cap,
        CAST(coin_data ->> 'total_volume' AS NUMERIC) AS total_volume,
        CAST(coin_data ->> 'high_24h' AS NUMERIC) AS high_24h,
        CAST(coin_data ->> 'low_24h' AS NUMERIC) AS low_24h,
        CAST(coin_data ->> 'price_change_percentage_24h' AS NUMERIC) AS price_change_pct_24h,
        CAST(coin_data ->> 'last_updated' AS TIMESTAMP) AS market_updated_at
    FROM source
),

deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY coin_id, market_updated_at 
            ORDER BY ingested_at DESC
        ) AS row_num
    FROM flattened
)

SELECT
    md5(coin_id || '-' || TO_CHAR(market_updated_at, 'YYYYMMDDHH24MISS')) AS market_data_id,
    coin_id,
    vs_currency,
    current_price,
    market_cap,
    total_volume,
    high_24h,
    low_24h,
    price_change_pct_24h,
    market_updated_at,
    ingested_at

FROM deduplicated
WHERE row_num = 1