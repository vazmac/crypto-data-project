-- Criar os schemas
CREATE SCHEMA IF NOT EXISTS raw;

-- Criar tabela com lista de moedas a monitorar
CREATE TABLE IF NOT EXISTS raw.cfg_watchlist (
    symbol VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    is_active BOOLEAN,
    last_updated TIMESTAMP
);

-- Tabela para os dados raw de Sustentabilidade
CREATE TABLE IF NOT EXISTS raw.esg_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50),
    esg_data JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela para os dados raw de mercado da CoinGecko
CREATE TABLE IF NOT EXISTS raw.coingecko_market_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    vs_currency VARCHAR(10) DEFAULT 'usd',
    last_updated TIMESTAMP,
    market_data JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_esg_data_symbol 
ON raw.esg_data (symbol, ingested_at);

CREATE INDEX IF NOT EXISTS idx_coingecko_market_data_symbol 
ON raw.coingecko_market_data (symbol, ingested_at);