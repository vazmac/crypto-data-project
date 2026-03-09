import os
import json
import requests
from datetime import datetime, timezone
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from psycopg2.extras import execute_values
from pydantic import BaseModel, ValidationError
from typing import Optional

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
FOLDER_NAME = "esg_metrics"
URL_ESG_API = "https://indices.carbon-ratings.com/api/currencies/tabledata"
SCHEMA_LANDING = "raw"
TABELA_MESTRA = "cfg_watchlist"

# --- Data Contract para validação dos dados da API ESG ---
class ESGContract(BaseModel):
    ticker: str
    name: Optional[str] = None
    marketcap: Optional[float] = None
    power: Optional[float] = None
    consumption: Optional[float] = None
    emission: Optional[float] = None

def extract_esg_to_s3(**context):
    """Extrai os dados de sustentabilidade, valida o schema e guarda o JSON no bucket."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}   # Evita bloqueios por parte do servidor da API ESG.
    print(f"🚀 A extrair dados da API ESG: {URL_ESG_API}")
    
    response = requests.get(URL_ESG_API, headers=headers, timeout=30)
    response.raise_for_status()
    raw_data = response.json()
    
    # Validação do Data Contract e inserção do Timestamp de Ingestão
    print("🛡️ A validar dados ESG contra o Data Contract...")
    cleaned_data = []
    ingested_at = datetime.now(timezone.utc).isoformat()

    for row in raw_data:
        try:
            valid_row = ESGContract(**row)
            
            ticker_clean = valid_row.ticker.strip().lower()
            if not ticker_clean:
                continue
            
            cleaned_data.append({
                "symbol": ticker_clean,
                "name": valid_row.name or ticker_clean,
                "marketcap": valid_row.marketcap,
                "electrical_power_kw": valid_row.power,
                "electricity_consumption_kwh": valid_row.consumption,
                "co2_emissions_kg": valid_row.emission,
                "ingested_at": ingested_at
            })
            
        except ValidationError as e:
            print(f"🚨 ERRO CRÍTICO: O Data Contract foi quebrado na API ESG!")
            print(f"Detalhes técnicos do erro:\n{e}")
            raise ValueError("Pipeline abortada: A estrutura da API da Carbon Ratings mudou!")

    print(f"💎 Extraídos e validados dados ESG de {len(cleaned_data)} moedas.")

    # Guardar no S3 (Data Lake)
    ts = context['ts_nodash']
    s3_key = f"{FOLDER_NAME}/{ts}.json"
    
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    if not s3_hook.check_for_bucket(BUCKET_NAME):
        s3_hook.create_bucket(BUCKET_NAME) 
        
    s3_hook.load_string(
        string_data=json.dumps(cleaned_data),
        key=s3_key,
        bucket_name=BUCKET_NAME,
        replace=True
    )
    
    print(f"✅ Upload ESG feito para s3://{BUCKET_NAME}/{s3_key}")
    return s3_key # Passa a chave para a função seguinte via XCom


def update_master_table_from_s3(**context):
    """Lê o JSON do S3 e atualiza a Tabela Mestra (cfg_watchlist) no Postgres."""
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='1_Extract_to_DataLake.extract_esg')
    
    if not s3_key:
        raise ValueError("❌ Erro: Nenhum ficheiro S3 recebido da task de extração ESG.")

    # Proteção Anti-Backfill
    data_execucao = context['logical_date'].date()
    data_hoje = datetime.now(timezone.utc).date()
    
    if data_execucao < data_hoje:
        print(f"⚠️ Backfill detetado ({data_execucao}). Tabela Mestra NÃO será atualizada.")
        return

    # Ler do S3
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    content = s3_hook.read_key(key=s3_key, bucket_name=BUCKET_NAME)
    esg_data = json.loads(content)
    
    # Atualizar Postgres (SCD Tipo 1)
    print("⚙️ A executar MERGE (Full Sync) na Tabela Mestra...")
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    merge_query = f"""
        MERGE INTO {SCHEMA_LANDING}.{TABELA_MESTRA} AS target
        USING (VALUES %s) AS source(symbol, name)
        ON target.symbol = source.symbol
        WHEN MATCHED THEN
            UPDATE SET is_active = TRUE, last_updated = NOW()
        WHEN NOT MATCHED THEN
            INSERT (symbol, name, is_active, last_updated)
            VALUES (source.symbol, source.name, TRUE, NOW())
        WHEN NOT MATCHED BY SOURCE THEN
            UPDATE SET is_active = FALSE, last_updated = NOW();
    """
    
    records_to_merge = [(row.get("symbol"), row.get("name")) for row in esg_data if row.get("symbol")]
    
    if records_to_merge:
        # O execute_values substitui o '%s' na query pela lista records_to_merge.
        execute_values(cursor, merge_query, records_to_merge)
        conn.commit()
        print(f"🎉 Tabela Mestra sincronizada na perfeição com {len(records_to_merge)} moedas da API!")
    else:
        print("⚠️ A lista da API estava vazia, nenhuma alteração feita.")

    cursor.close()
    conn.close()