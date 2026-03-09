WITH source AS (
    SELECT * FROM {{ source('raw_data', 'coingecko_market_data') }}
),

silver_coingecko AS (
    SELECT
        id AS raw_market_id,
        symbol,
        vs_currency AS currency,
        last_updated,
        ingested_at,
        (market_data->>'current_price')::numeric AS current_price,
        (market_data->>'market_cap')::numeric AS market_cap,
        (market_data->>'total_volume')::numeric AS total_volume,
        (market_data->>'high_24h')::numeric AS high_24h,
        (market_data->>'low_24h')::numeric AS low_24h,
        (market_data->>'price_change_percentage_24h')::numeric AS price_change_pct_24h

    FROM source
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY symbol, currency, DATE(ingested_at) ORDER BY ingested_at DESC) AS rn
    FROM silver_coingecko
)

SELECT
    raw_market_id,
    symbol,
    currency,
    last_updated,
    ingested_at,
    current_price,
    market_cap,
    total_volume,
    high_24h,
    low_24h,
    price_change_pct_24h
FROM deduped
WHERE rn = 1