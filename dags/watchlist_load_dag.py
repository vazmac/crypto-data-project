from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Scripts python
from scripts.extract_watchlist import extract_trending_to_s3, create_watchlist_from_s3

default_args = {
    'owner': 'data_engineer',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'watchlist_load',
    default_args=default_args,
    description='Popula a Watchlist com Top 15 Trending Coins',
    schedule_interval='@once',  # Fazemos apenas um run para popular a watchlist inicialmente
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['production', 'watchlist', 'setup']
) as dag:

    # --- 1. Extração da API para o S3 ---
    t1 = PythonOperator(
        task_id='extract_trending',
        python_callable=extract_trending_to_s3,
    )

    # --- 2. Carregamento do S3 para a tabela Watchlist ---
    t2 = PythonOperator(
        task_id='create_watchlist',
        python_callable=create_watchlist_from_s3,
    )

    # 🔗 DEFINIÇÃO DA ORDEM DE EXECUÇÃO
    t1 >> t2