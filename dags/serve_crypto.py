from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine
import os

# --- CONFIGURAÇÕES ---
# 1. Diretórios dinâmicos
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DBT_DIR = f"{PROJECT_DIR}/transform_crypto"
DASHBOARD_DIR = f"{PROJECT_DIR}/dashboard_data"

# 2. Base de Dados
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "coingecko_dw")

SCHEMA_GOLD = "gold"
TABELA_GOLD = "fct_daily_metrics"

# --- 1. Função para Exportar para CSV ---
def serve_gold_to_csv(**context):

    execution_date = context['ds']
    
    engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
    
    print("A extrair dados da camada Gold...")
    df = pd.read_sql(f"SELECT * FROM {SCHEMA_GOLD}.{TABELA_GOLD}", engine)
    
    filename = f'crypto_dashboard_{execution_date}.csv'
    output_path = os.path.join(DASHBOARD_DIR, filename)
    
    df.to_csv(output_path, index=False)
    print(f"✅ Sucesso! Ficheiro guardado em: {output_path}")

# --- 2. Configurações da DAG ---
default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1), 
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'crypto_daily_pipeline',
    default_args=default_args,
    description='Pipeline End-to-End: Extração -> dbt (Silver/Gold) -> Exportar CSV',
    schedule_interval='@daily', 
    catchup=False,
) as dag:
    # Passo 1: Trigger do DAG de Extração
    trigger_extraction = TriggerDagRunOperator(
        task_id='trigger_extraction_dag',
        trigger_dag_id='extraction',
        wait_for_completion=True,
        poke_interval=30,
    )

    # Passo 2: Correr os modelos dbt
    run_dbt = BashOperator(
        task_id='dbt_run',
        bash_command=f'cd {DBT_DIR} && dbt run --profiles-dir .',
    )

    # Passo 3: Testar os dados no dbt
    test_dbt = BashOperator(
        task_id='dbt_test',
        bash_command=f'cd {DBT_DIR} && dbt test --profiles-dir .',
    )

    # Passo 4: Exportar a tabela Gold para CSV
    serve_csv = PythonOperator(
        task_id='serve_gold_to_csv',
        python_callable=serve_gold_to_csv,
        provide_context=True,
    )

    # --- 3. Definir a Ordem de Execução (O Lineage) ---
    trigger_extraction >> run_dbt >> test_dbt >> serve_csv