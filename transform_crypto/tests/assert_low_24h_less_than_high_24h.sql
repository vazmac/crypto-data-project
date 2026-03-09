-- Queremos apanhar as anomalias: linhas onde o mínimo diário é MAIOR que o máximo diário
SELECT
    coin_symbol,
    current_date,
    low_24h,
    high_24h
FROM {{ ref('fct_daily_metrics') }}
WHERE low_24h > high_24h