import os
import json
import requests
from datetime import datetime
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("DATA_LAKE_BUCKET", "coingecko-raw")
BASE_URL = os.getenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")
API_KEY = Variable.get("coingecko_api_key", default_var=None)
SCHEMA_LANDING = "raw"
TABELA_WATCHLIST = "coin_watchlist"

def extract_trending_to_s3(**context):
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
        
        # Obter coins
        trending_list = full_json.get('coins', [])
        
        print(f"💎 Encontradas {len(trending_list)} moedas em tendência.")

        # Guardar no S3
        ts = context['ts_nodash']
        s3_key = f"trending/{ts}.json"
        
        s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
        if not s3_hook.check_for_bucket(BUCKET_NAME):
            print(f"🪣 Bucket {BUCKET_NAME} não encontrado. A criar...")
            s3_hook.create_bucket(BUCKET_NAME) 
            
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
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='extract_trending')
    
    if not s3_key:
        print("❌ Nenhum ficheiro gerado.")
        return

    # --- 1. PREPARAR POSTGRES E VERIFICAR SE A TABELA ESTÁ VAZIA ---
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(1) FROM {SCHEMA_LANDING}.{TABELA_WATCHLIST};")
    row_count = cursor.fetchone()[0]
    
    if row_count > 0:
        print(f"🛑 Operação cancelada: A tabela {TABELA_WATCHLIST} já contém {row_count} moedas.")
        print("A manter a Watchlist original intacta.")
        cursor.close()
        conn.close()
        return # Se a tabela não estiver vazia, não fazemos nada. A ideia é só popular a watchlist uma vez, e depois deixá-la ser atualizada manualmente ou por outro processo específico.

    # --- 2. SE ESTIVER VAZIA, LÊ DO S3 ---
    print("✅ A tabela está vazia. A iniciar inserção da nova Watchlist...")
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    content = s3_hook.read_key(key=s3_key, bucket_name=BUCKET_NAME)
    trending_data = json.loads(content)
    
    insert_query = f"""
        INSERT INTO {SCHEMA_LANDING}.{TABELA_WATCHLIST} (coin_id, name, symbol, market_cap_rank, ingested_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (coin_id) DO NOTHING;
    """
    
    inserted_count = 0

    # --- 3. ITERAR E INSERIR ---
    for entry in trending_data:
        item = entry.get('item', {})
        
        c_id = item.get('id')
        c_name = item.get('name')
        c_symbol = item.get('symbol')
        c_rank = item.get('market_cap_rank')
        
        if c_id:
            cursor.execute(insert_query, (c_id, c_name, c_symbol, c_rank))
            inserted_count += 1
            
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"🎉 Watchlist criada do zero! {inserted_count} moedas adicionadas.")