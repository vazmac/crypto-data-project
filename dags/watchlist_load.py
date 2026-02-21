from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable
from datetime import datetime, timedelta
import requests
import json
import os

# --- CONFIGURAÇÕES ---
# Usamos as mesmas variáveis de ambiente para manter coerência
BUCKET_NAME = os.getenv("DATA_LAKE_BUCKET", "coingecko-raw")
BASE_URL = os.getenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")
API_KEY = Variable.get("coingecko_api_key", default_var=None)
SCHEMA_LANDING = "raw"
TABELA_WATCHLIST = "coin_watchlist"

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def extract_trending_to_s3(**context):
    """
    1. Chama API Trending.
    2. Extrai a lista ['coins'].
    3. Guarda no S3.
    """
    endpoint = "/search/trending"
    url = f"{BASE_URL}{endpoint}"
    
    headers = {"accept": "application/json"}
    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    print(f"🚀 A contactar {url}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        full_json = response.json()
        
        # A API devolve { "coins": [...], "nfts": [...] }
        # Nós só queremos as coins
        trending_list = full_json.get('coins', [])
        
        print(f"💎 Encontradas {len(trending_list)} moedas em tendência.")

        # Guardar no S3
        ts = context['ts_nodash']
        s3_key = f"trending/{ts}.json"
        
        s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
        # Verificar se o bucket existe, se não, criar e fazer upload
        if not s3_hook.check_for_bucket(BUCKET_NAME):
            print(f"🪣 Bucket {BUCKET_NAME} não encontrado. A criar...")
            s3_hook.create_bucket(BUCKET_NAME) # não é a melhor prática, deveria ser feito via IaC, mas para garantir que o bucket existe, vamos criar aqui se necessário.
        s3_hook.load_string(
            string_data=json.dumps(trending_list),
            key=s3_key,
            bucket_name=BUCKET_NAME,
            replace=True
        )
        
        print(f"✅ Upload feito para s3://{BUCKET_NAME}/{s3_key}")
        return s3_key

    except Exception as e:
        print(f"❌ Erro ao extrair trending: {e}")
        raise e

def create_watchlist_from_s3(**context):
    """
    1. Lê o ficheiro do S3.
    2. Faz UPSERT na tabela raw.coin_watchlist.
    """
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='extract_trending')
    
    if not s3_key:
        print("❌ Nenhum ficheiro gerado.")
        return

    # 1. Ler do S3
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    content = s3_hook.read_key(key=s3_key, bucket_name=BUCKET_NAME)
    trending_data = json.loads(content)

    # 2. Preparar Postgres
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    # Query Inteligente: Tenta inserir, se já existir (conflito de ID), não faz nada.
    insert_query = f"""
        INSERT INTO {SCHEMA_LANDING}.{TABELA_WATCHLIST} (coin_id, name, symbol, market_cap_rank, ingested_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (coin_id) DO NOTHING;
    """
    
    inserted_count = 0

    # 3. Iterar sobre a lista da API
    for entry in trending_data:
        item = entry.get('item', {})
        
        c_id = item.get('id')
        c_name = item.get('name')
        c_symbol = item.get('symbol')
        c_rank = item.get('market_cap_rank')
        
        # Só inserimos se tivermos pelo menos o ID
        if c_id:
            cursor.execute(insert_query, (c_id, c_name, c_symbol, c_rank))
            inserted_count += 1
            
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ Watchlist criada! {inserted_count} novas moedas adicionadas.")

with DAG(
    'watchlist_load',
    default_args=default_args,
    description='Popula a Watchlist com Top 15 Trending Coins',
    schedule_interval='@once',  # fazemos apenas um run para popular a watchlist inicialmente
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['production', 'watchlist']
) as dag:

    t1 = PythonOperator(
        task_id='extract_trending',
        python_callable=extract_trending_to_s3,
        provide_context=True
    )

    t2 = PythonOperator(
        task_id='create_watchlist',
        python_callable=create_watchlist_from_s3,
        provide_context=True
    )

    t1 >> t2