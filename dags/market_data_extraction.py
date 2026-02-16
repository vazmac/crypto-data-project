from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.models import Variable
from datetime import datetime, timedelta
import requests
import json
import csv
import io
import os

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("DATA_LAKE_BUCKET")
API_KEY = Variable.get("coingecko_api_key", default_var=None)
CURRENCY = Variable.get("coingecko_currency", default_var="eur")
BASE_URL = os.getenv("COINGECKO_BASE_URL")

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def extract_and_transform_to_csv(**context):
    """
    1. Lê Watchlist (Postgres).
    2. API Call (CoinGecko).
    3. Converte JSON -> CSV em memória (IO) para possibilitar write em bulk mode no Postgres.
    4. Upload CSV para S3.
    """
    # --- A. Obter Moedas da Watchlist ---
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    records = pg_hook.get_records("SELECT coin_id FROM dh_raw.coin_watchlist;")
    
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
    # Criamos um "ficheiro virtual" na RAM. Super rápido.
    csv_buffer = io.StringIO()
    
    # Configuração CRÍTICA do CSV para lidar com JSONs lá dentro:
    # quotechar='"': Envolve campos complexos em aspas.
    # quoting=csv.QUOTE_MINIMAL: Só põe aspas se necessário (ex: se o JSON tiver virgulas).
    csv_writer = csv.writer(csv_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    ingested_at = datetime.now().isoformat()

    count = 0
    for coin in data:
        # Extrair dados chave para colunas dedicadas
        c_id = coin.get('id')
        last_updated = coin.get('last_updated')
        
        # Serializar o objeto inteiro para string
        json_str = json.dumps(coin)
        
        # Escrever linha no Buffer
        # ORDEM: coin_id, vs_currency, ingested_at, last_updated_api, coin_data
        csv_writer.writerow([c_id, CURRENCY, ingested_at, last_updated, json_str])
        count += 1

    # --- D. Upload para S3 ---
    ts = context['ts_nodash'] # definimos a unicidade do ficheiro com o timestamp do Airflow (sem caracteres especiais)
    filename = f"market_data_bulk/{ts}.csv"
    
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    s3_hook.load_string(
        string_data=csv_buffer.getvalue(), # O conteúdo do buffer
        key=filename,
        bucket_name=BUCKET_NAME,
        replace=True
    )
    
    print(f"✅ CSV gerado ({count} linhas) e enviado: s3://{BUCKET_NAME}/{filename}")
    return filename

def load_csv_to_postgres(**context):
    """
    1. Download Stream do CSV (S3).
    2. Executar COPY command (Postgres Bulk Load).
    """
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='extract_to_csv')
    
    if not s3_key:
        print("❌ Nenhum ficheiro para processar.")
        return

    # --- A. Ler do S3 como Stream ---
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    obj = s3_hook.get_key(key=s3_key, bucket_name=BUCKET_NAME)
    file_content = obj.get()['Body'].read().decode('utf-8')
    
    # Converter string para File-like object para o Postgres ler
    f = io.StringIO(file_content)

    # --- B. Comando COPY (Bulk Load) ---
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    # O comando mágico que faz o mapeamento CSV -> Tabela
    sql = """
        COPY dh_raw.market_data (coin_id, vs_currency, ingested_at, last_updated, coin_data)
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

with DAG(
    'extraction',
    default_args=default_args,
    description='Pipeline Escalável: API -> CSV(S3) -> COPY(Postgres)',
    schedule_interval='@hourly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['production', 'extraction', 'market_data']
) as dag:

    t1 = PythonOperator(
        task_id='extract_to_csv',
        python_callable=extract_and_transform_to_csv,
        provide_context=True
    )

    t2 = PythonOperator(
        task_id='load_to_postgres',
        python_callable=load_csv_to_postgres,
        provide_context=True
    )

    t1 >> t2