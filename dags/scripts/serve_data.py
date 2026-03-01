import os
import pandas as pd
from sqlalchemy import create_engine

# --- CONFIGURAÇÕES ---
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DASHBOARD_DIR = f"{PROJECT_DIR}/dashboard_data"

DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "coingecko_dw")

SCHEMA_GOLD = "gold"
TABELA_GOLD = "fct_daily_metrics"

def serve_gold_to_csv(**context):
    execution_date = context['ds']
    engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
    
    print("A extrair dados da camada Gold...")
    df = pd.read_sql(f"SELECT * FROM {SCHEMA_GOLD}.{TABELA_GOLD}", engine)
    
    filename = f'crypto_dashboard_{execution_date}.csv'
    output_path = os.path.join(DASHBOARD_DIR, filename)
    
    df.to_csv(output_path, index=False)
    print(f"✅ Sucesso! Ficheiro guardado em: {output_path}")