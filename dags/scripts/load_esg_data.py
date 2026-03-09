import os
import json
import csv
import io
from datetime import datetime, timezone
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# --- CONFIGURAÇÕES ---
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "datalake-raw")
SCHEMA_LANDING = "raw"
TABELA_ESG = "esg_data"

def load_esg_to_postgres(**context):
    """
    Lê os dados de Sustentabilidade (ESG) do MinIO, empacota o JSON de cada moeda
    numa estrutura CSV em memória, e faz COPY para a coluna JSONB do Postgres.
    """
    ti = context['ti']
    s3_key = ti.xcom_pull(task_ids='1_Extract_to_DataLake.extract_esg') 
    
    if not s3_key:
        raise ValueError("❌ Erro: Nenhum ficheiro S3 de ESG recebido da task anterior.")

    # 1. Ler do S3
    print(f"📥 A ler {s3_key} do MinIO...")
    s3_hook = S3Hook(aws_conn_id='minio_s3_conn')
    file_content = s3_hook.read_key(key=s3_key, bucket_name=BUCKET_NAME)
    data = json.loads(file_content)
    
    if not data:
        print("⚠️ Ficheiro vazio ou sem dados válidos.")
        return

    # 2. Transformação JSON -> CSV (In-Memory)
    print("⚙️ A preparar o buffer CSV em memória para os dados ESG...")
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    ingested_at = datetime.now(timezone.utc).isoformat()

    count = 0
    for coin in data:
        c_symbol = coin.get('symbol')
        
        if not c_symbol:
            continue
            
        # Transformar o dicionário numa string JSON válida para a coluna JSONB
        esg_data = json.dumps(coin) 
        
        # Escrevemos a linha com a ordem exata para o COPY: (symbol, esg_data, ingested_at)
        csv_writer.writerow([c_symbol, esg_data, ingested_at])
        count += 1

    # Voltar o "cursor" da memória ao início para o Postgres conseguir ler
    csv_buffer.seek(0)

    # 3. Bulk Insert (COPY) no Postgres
    print(f"🚀 A fazer Bulk Insert (COPY) de {count} registos para {SCHEMA_LANDING}.{TABELA_ESG}...")
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    # Especificamos as colunas alvo (ignoramos o 'id' que é SERIAL)
    copy_query = f"""
        COPY {SCHEMA_LANDING}.{TABELA_ESG} 
        (symbol, esg_data, ingested_at) 
        FROM STDIN WITH CSV
    """
    
    try:
        # Usamos o cursor nativo do psycopg2, que aceita StringIO
        cursor.copy_expert(copy_query, csv_buffer)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    
    print(f"✅ Sucesso!")