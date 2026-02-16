# Crypto Data Project

Um pipeline de dados escalável para extração, transformação e carga (ELT) de dados de criptomoedas usando **Apache Airflow**, **PostgreSQL**, **MinIO (S3)** e **dbt**.

## 🏗️ Arquitetura

```
CoinGecko API → Airflow (Orquestração) → MinIO (Data Lake) → PostgreSQL (DW) → dbt (Transformação)
```

## 📁 Estrutura do Projeto

```
crypto_data_project/
├── dags/                          # DAGs do Airflow
│   ├── watchlist_load.py         # Carrega top 15 moedas em tendência
│   └── market_data_extraction.py # Extrai dados de mercado em lote
├── scripts/init_db.sql           # Script de inicialização do banco
├── dbt_project/                  # Modelos de transformação (dbt)
├── docker-compose.yml            # Infraestrutura containerizada
├── DockerFile                    # Imagem customizada do Airflow
├── requirements.txt              # Dependências Python
├── servers.json                  # Configuração PGAdmin
└── .env                          # Variáveis de ambiente
```

## 🚀 Quick Start

### 1. Pré-requisitos
- Docker & Docker Compose
- Windows PowerShell (para o script de inicialização)

### 2. Configurar Variáveis de Ambiente
Cria um arquivo `.env` na raiz do projeto:

```env
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow123
POSTGRES_DB=coingecko_dw
POSTGRES_PORT=5432
POSTGRES_HOST=postgres

PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=admin
PGADMIN_PORT=5050

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_PORT_API=9000
MINIO_PORT_CONSOLE=9001
MINIO_BUCKET_NAME=coingecko-raw

AIRFLOW_PORT=8080
AIRFLOW_SECRET_KEY=your-secret-key-here
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_ADMIN_EMAIL=admin@example.com

COINGECKO_API_KEY=your-api-key
COINGECKO_CURRENCY=eur
COINGECKO_BASE_URL=https://api.coingecko.com/api/v3
```

### 3. Iniciar Infraestrutura (Windows)
```powershell
.\start_docker.ps1
```

Ou manualmente:
```bash
docker-compose up -d
```

## 🌐 Acessos

| Serviço | URL |
|---------|-----|
| Airflow | http://localhost:8080 |
| PGAdmin | http://localhost:5050 |
| MinIO Console | http://localhost:9001 |

## 📊 DAGs Disponíveis

### `watchlist_load`
- Extrai top 15 moedas em tendência do CoinGecko
- Popula tabela `dh_raw.coin_watchlist`
- **Frequência:** Uma única execução

### `extraction`
- Extrai dados de mercado de todas as moedas da watchlist
- Transforma JSON → CSV e faz upload para MinIO
- Carrega dados em `dh_raw.market_data` via COPY (bulk load)
- **Frequência:** A cada hora

## 🏢 Camadas de Dados

```sql
dh_raw       -- Dados brutos da API (ingestão)
dh_silver    -- Dados limpos e normalizados
dh_gold      -- Dados agregados para BI/Analytics
```

## 🔧 Tecnologias

- **Apache Airflow 2.8** - Orquestração
- **PostgreSQL 13** - Data Warehouse
- **MinIO** - Data Lake (S3-compatible)
- **dbt** - Transformação de dados
- **Docker Compose** - Infraestrutura como código

## 📝 Notas

- Os dados são ingeridos em formato JSONB para máxima flexibilidade
- Bulk insert via COPY command para performance
- Retry automático com delay de 5 minutos em caso de falha