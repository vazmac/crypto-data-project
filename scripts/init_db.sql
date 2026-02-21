-- Criar os schemas
CREATE SCHEMA IF NOT EXISTS raw;

-- Criar tabela com lista de moedas a monitorar (Top 15 trending coins da API do CoinGecko na primeira execução)
CREATE TABLE IF NOT EXISTS raw.coin_watchlist (
    coin_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255),
    symbol VARCHAR(50),
    market_cap_rank INT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Factos: Dados de mercado das criptomoedas (preço, volume, etc) em formato JSONB
CREATE TABLE IF NOT EXISTS raw.market_data (
    id SERIAL PRIMARY KEY,
    coin_id VARCHAR(100) NOT NULL,
    vs_currency VARCHAR(10) DEFAULT 'eur',
    last_updated TIMESTAMP,
    coin_data JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_data_coin_time 
ON raw.market_data (coin_id, ingested_at DESC);