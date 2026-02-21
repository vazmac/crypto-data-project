WITH source AS (
    SELECT * FROM {{ source('coingecko', 'coin_watchlist') }}
)

SELECT
    coin_id,
    symbol,
    name,
    market_cap_rank,
    ingested_at
FROM source