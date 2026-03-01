import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# python scripts
from scripts.extract_market_data import extract_and_transform_to_csv, load_csv_to_postgres
from scripts.serve_data import serve_gold_to_csv

# --- CONFIGURAÇÕES GERAIS ---
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DBT_DIR = f"{PROJECT_DIR}/transform_crypto"

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1), 
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'crypto_end_to_end_pipeline',
    default_args=default_args,
    description='Pipeline ELT Completo: API -> MinIO -> Postgres -> dbt -> CSV',
    schedule_interval='@daily', 
    catchup=False,
    tags=['production', 'pipeline', 'crypto', 'daily']
) as dag:

    # --- 1. EXTRAÇÃO (CoinGecko para MinIO) ---
    extract_to_s3 = PythonOperator(
        task_id='extract_to_csv',
        python_callable=extract_and_transform_to_csv,
    )

    # --- 2. CARREGAMENTO (MinIO para Postgres Raw) ---
    load_to_db = PythonOperator(
        task_id='load_to_postgres',
        python_callable=load_csv_to_postgres,
    )

    # --- 3. TRANSFORMAÇÃO (dbt: Raw -> Silver -> Gold) ---
    run_dbt = BashOperator(
        task_id='dbt_run',
        bash_command=f'cd {DBT_DIR} && dbt run --profiles-dir .',
    )

    # --- 4. TESTES (dbt test) ---
    test_dbt = BashOperator(
        task_id='dbt_test',
        bash_command=f'cd {DBT_DIR} && dbt test --profiles-dir .',
    )

    # --- 5. EXPORTAÇÃO (Gold para PowerBI CSV) ---
    export_csv = PythonOperator(
        task_id='serve_gold_to_csv',
        python_callable=serve_gold_to_csv,
    )

    # 🔗 DEFINIÇÃO DA ORDEM DE EXECUÇÃO
    extract_to_s3 >> load_to_db >> run_dbt >> test_dbt >> export_csv