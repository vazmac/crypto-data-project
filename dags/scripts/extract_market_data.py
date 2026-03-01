import os
import io
import csv
import json
import requests
from datetime import datetime
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("DATA_LAKE_BUCKET")
API_KEY = Variable.get("COINGECKO_API_KEY", default_var=None)
CURRENCY = Variable.get("COINGECKO_CURRENCY", default_var="usd")
BASE_URL = os.getenv("COINGECKO_BASE_URL")
SCHEMA_LANDING = "raw"
TABELA_WATCHLIST = "coin_watchlist"
TABELA_MARKET_DATA = "market_data"

def extract_and_transform_to_csv(**context):
    # --- A. Obter Moedas da Watchlist ---
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    records = pg_hook.get_records(f"SELECT coin_id FROM {SCHEMA_LANDING}.{TABELA_WATCHLIST};")
    
    if not records:
        print("⚠️ Watchlist vazia! Corre o DAG watchlist_load primeiro.")
        return None

    ids_list = [r[0] for r in records]
    ids_string = ",".join(ids_list)
    
    # --- B. Chamar API ---
    endpoint = "/coins/markets"
    url = f"{BASE_URL}{endpoint}"
    params = {
        'vs_currency': CURRENCY,
        'ids': ids_string,
        'order': 'market_cap_desc',
        'per_page': 250,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '1h'
    }
    
    headers = {"accept": "application/json"}
    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    print(f"🚀 A pedir dados para {len(ids_list)} moedas...")
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # --- C. Transformação JSON -> CSV (In-Memory) ---
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    ingested_at = datetime.now().isoformat()

    count = 0
    for coin in data:
        c_id = coin.get('id')
        last_updated = coin.get('last_updated')
        json_str = json.dumps(coin)
        csv_writer.writerow([c_id, CURRENCY, ingested_at, last_updated, json_str])
        count += 1

    # --- D. Upload para S3 ---
    ts = context['ts_nodash']
    filename = f"market_data_bulk/{ts}.csv"
    
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    s3_hook.load_string(
        string_data=csv_buffer.getvalue(),
        key=filename,
        bucket_name=BUCKET_NAME,
        replace=True
    )
    
    print(f"✅ CSV gerado ({count} linhas) e enviado: s3://{BUCKET_NAME}/{filename}")
    return filename

def load_csv_to_postgres(**context):
    ti = context['ti']
    # ATENÇÃO: Este task_id tem de bater certo com o que definimos na DAG!
    s3_key = ti.xcom_pull(task_ids='extract_to_csv') 
    
    if not s3_key:
        print("❌ Nenhum ficheiro para processar.")
        return

    # --- A. Ler do S3 como Stream ---
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    obj = s3_hook.get_key(key=s3_key, bucket_name=BUCKET_NAME)
    file_content = obj.get()['Body'].read().decode('utf-8')
    f = io.StringIO(file_content)

    # --- B. Comando COPY (Bulk Load) ---
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    sql = f"""
        COPY {SCHEMA_LANDING}.{TABELA_MARKET_DATA} (coin_id, vs_currency, ingested_at, last_updated, coin_data)
        FROM STDIN WITH (FORMAT CSV, HEADER FALSE, DELIMITER ',', QUOTE '"');
    """
    
    print("🚀 A executar COPY para o Postgres...")
    try:
        cursor.copy_expert(sql, f)
        conn.commit()
        print("✅ Carga completa com sucesso!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no COPY: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()