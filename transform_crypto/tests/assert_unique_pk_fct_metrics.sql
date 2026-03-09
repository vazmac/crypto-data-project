-- Agrupar pela chave composta e encontrar quem tem mais de 1 registo
SELECT
    coin_symbol,
    current_date,
    COUNT(*) as total_registos
FROM {{ ref('fct_daily_metrics') }}
GROUP BY 
    coin_symbol, 
    current_date
HAVING COUNT(*) > 1