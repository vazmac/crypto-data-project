WITH daily_snapshot AS (
    -- 1. Obter apenas 1 registo por dia (o "fecho" do dia) para garantir métricas limpas
    SELECT
        coin_id,
        DATE(market_updated_at) AS metric_date,
        current_price,
        total_volume,
        price_change_pct_24h,
        ROW_NUMBER() OVER (
            PARTITION BY coin_id, DATE(market_updated_at) 
            ORDER BY market_updated_at DESC
        ) AS rn
    FROM {{ ref('stg_market_data') }}
),

eod_prices AS (
    -- Filtramos para ficar só com a última foto de cada dia
    SELECT * FROM daily_snapshot 
    WHERE rn = 1
),

rolling_calculations AS (
    -- 2. Calcular os valores do passado (Lags e Rolling Averages)
    SELECT
        coin_id,
        metric_date,
        current_price,
        total_volume,
        price_change_pct_24h,
        
        -- Preço do dia anterior para calcular o retorno
        LAG(current_price) OVER (
            PARTITION BY coin_id 
            ORDER BY metric_date
        ) AS prev_price,
        
        -- Média Móvel de 7 dias (inclui o dia atual + 6 anteriores)
        AVG(current_price) OVER (
            PARTITION BY coin_id 
            ORDER BY metric_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS price_7d_avg,
        
        -- Média Móvel de 30 dias
        AVG(current_price) OVER (
            PARTITION BY coin_id 
            ORDER BY metric_date 
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS price_30d_avg,

        -- Média Móvel do Volume (7 dias) para ver tendências de mercado
        AVG(total_volume) OVER (
            PARTITION BY coin_id 
            ORDER BY metric_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS volume_7d_avg

    FROM eod_prices
)

-- 3. Juntar tudo e calcular as percentagens finais
SELECT
    -- Criamos uma chave primária para esta tabela Gold
    md5(coin_id || '-' || metric_date::text) AS fact_id,
    
    coin_id,
    metric_date,
    current_price,
    total_volume,
    price_change_pct_24h,
    
    -- Retorno Diário: (Preço Atual - Preço Anterior) / Preço Anterior
    CASE 
        WHEN prev_price IS NULL OR prev_price = 0 THEN 0 
        ELSE (current_price - prev_price) / prev_price 
    END AS daily_return_pct,
    
    price_7d_avg,
    price_30d_avg,
    volume_7d_avg,
    
    -- Métrica Extra: Quão longe estamos da média de 30 dias? (Bom para ver picos irreais)
    CASE 
        WHEN price_30d_avg IS NULL OR price_30d_avg = 0 THEN 0
        ELSE (current_price - price_30d_avg) / price_30d_avg
    END AS distance_from_30d_avg_pct

FROM rolling_calculations
-- Opcional: ORDER BY metric_date DESC, coin_id