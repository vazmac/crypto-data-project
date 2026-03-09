{{ config(materialized='table') }}

WITH daily_prices AS (
    SELECT * FROM {{ ref('stg_coingecko_market_data') }}
),

daily_esg AS (
    SELECT * FROM {{ ref('stg_esg_data') }}
),

joined_metrics AS (
    SELECT
        p.symbol AS coin_symbol,
        DATE(p.ingested_at) AS current_date,
        p.current_price,
        p.high_24h,
        p.low_24h,
        ROUND(p.market_cap::NUMERIC, 2) AS market_cap,
        ROUND(p.total_volume::NUMERIC, 2) AS total_volume,
        ROUND(p.price_change_pct_24h::NUMERIC, 2) AS price_change_pct_24h,
        ROUND(e.electrical_power_kw::NUMERIC, 2) AS electrical_power_kw,
        ROUND(e.electricity_consumption_kwh::NUMERIC, 2) AS electricity_consumption_kwh,
        ROUND(e.co2_emissions_kg::NUMERIC, 2) AS co2_emissions_kg
        
    FROM daily_prices p
    LEFT JOIN daily_esg e 
        ON p.symbol = e.symbol 
        AND DATE(p.ingested_at) = DATE(e.ingested_at)
)

SELECT * FROM joined_metrics