import os
import io
import csv
import json
import requests
from datetime import datetime, timezone
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable
from pydantic import BaseModel, ValidationError
from typing import Optional

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
FOLDER_NAME = "coingecko_market_data"
API_KEY = Variable.get("COINGECKO_API_KEY", default_var=None)
CURRENCY = Variable.get("COINGECKO_CURRENCY", default_var="usd")
BASE_URL = os.getenv("COINGECKO_BASE_URL")
SCHEMA_LANDING = "raw"
TABELA_WATCHLIST = "cfg_watchlist"
TABELA_MARKET_DATA = "market_data"

# --- Data Contract para validação dos dados da API CoinGecko ---
class CoinGeckoContract(BaseModel):
    symbol: str
    current_price: float
    market_cap: float
    total_volume: float
    high_24h: Optional[float] = None    # A API da CoinGecko pode não devolver este campo para moedas menos líquidas
    low_24h: Optional[float] = None     # A API da CoinGecko pode não devolver este campo para moedas menos líquidas
    price_change_percentage_24h: Optional[float] = None
    last_updated: str

def extract_coingecko_to_s3(**context):
    # 1. Obter a Watchlist Ativa do Postgres
    print("🔍 A consultar a Tabela Mestra no Postgres...")
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    records = pg_hook.get_records(f"SELECT symbol FROM {SCHEMA_LANDING}.{TABELA_WATCHLIST} WHERE is_active = TRUE;")
    
    if not records:
        raise ValueError("❌ Missão abortada: Não há moedas ativas na cfg_watchlist.")

    symbols_list = [row[0] for row in records]
    symbols_string = ",".join(symbols_list)
    print(f"🎯 Moedas a extrair ({len(symbols_list)}): {symbols_string[:50]}...")
    
    # 2. Configurar a chamada à API
    endpoint = "/coins/markets"
    url = f"{BASE_URL}{endpoint}"
    params = {
        'vs_currency': CURRENCY,
        'symbols': symbols_string,
        'order': 'market_cap_desc',
        'per_page': 250,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '24h'
    }
    
    headers = {"accept": "application/json"}
    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    # 3. Extrair da Web
    print(f"🚀 A contactar CoinGecko...")
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    market_data = response.json()

    # 4. Validação do Data Contract e inserção do Timestamp de Ingestão
    validated_data = []
    ingested_at = datetime.now(timezone.utc).isoformat()

    print("🛡️ A validar dados contra o Data Contract...")
    for row in market_data:
        try:
            valid_row = CoinGeckoContract(**row)
            clean_row = valid_row.model_dump() 
            clean_row['ingested_at'] = ingested_at
            
            validated_data.append(clean_row)
            
        except ValidationError as e:
            print(f"🚨 ERRO CRÍTICO: O Data Contract foi quebrado!")
            print(f"Detalhes técnicos do erro:\n{e}")
            raise ValueError("Pipeline abortada: A estrutura da API da CoinGecko mudou!")

    print(f"📈 Preços validados e extraídos para {len(validated_data)} moedas.")

    # 5. Guardar no S3 (Data Lake)
    ts = context['ts_nodash']
    s3_key = f"{FOLDER_NAME}/{ts}.json" 
    
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    if not s3_hook.check_for_bucket(BUCKET_NAME):
        s3_hook.create_bucket(BUCKET_NAME)
    
    s3_hook.load_string(
        string_data=json.dumps(market_data),
        key=s3_key,
        bucket_name=BUCKET_NAME,
        replace=True
    )
    
    print(f"✅ Upload Market Data feito para s3://{BUCKET_NAME}/{s3_key}")
    return s3_key # Passa a chave para a função seguinte via XCom