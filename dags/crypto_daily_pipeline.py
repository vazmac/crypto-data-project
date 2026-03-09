import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, RenderConfig
from cosmos.profiles import PostgresUserPasswordProfileMapping
from cosmos.constants import TestBehavior

# python scripts
from scripts.extract_esg_data import extract_esg_to_s3, update_master_table_from_s3
from scripts.extract_coingecko_market_data import extract_coingecko_to_s3
from scripts.load_esg_data import load_esg_to_postgres
from scripts.load_coingecko_market_data import load_market_data_to_postgres
from scripts.serve_data import serve_gold_to_csv

# --- CONFIGURAÇÕES GERAIS ---
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DBT_DIR = f"{PROJECT_DIR}/transform_crypto"

with DAG(
    dag_id='crypto_enterprise_pipeline', 
    start_date=datetime(2026, 3, 1), 
    schedule_interval='@daily', 
    catchup=False,
    tags=['crypto', 'dbt', 'elt']
) as dag:

    # 1. BLOCO DE EXTRAÇÃO
    with TaskGroup('1_Extract_to_DataLake') as extract_group:
        t1 = PythonOperator(task_id='extract_esg', python_callable=extract_esg_to_s3)
        t2 = PythonOperator(task_id='update_master', python_callable=update_master_table_from_s3)
        t3 = PythonOperator(task_id='extract_coingecko', python_callable=extract_coingecko_to_s3)
        
        t1 >> t2 >> t3

    # 2. BLOCO DE LOAD
    with TaskGroup('2_Load_to_Postgres') as load_group:
        t4 = PythonOperator(task_id='load_esg', python_callable=load_esg_to_postgres)
        t5 = PythonOperator(task_id='load_prices', python_callable=load_market_data_to_postgres)
        
        # Correm em paralelo!
        [t4, t5]

    # 3. BLOCO DE TRANSFORMAÇÃO (dbt)
    with TaskGroup('3_Transform_with_dbt') as dbt_group:
        
        # Usamos o Cosmos para orquestrar os modelos dbt
        dbt_project = DbtTaskGroup(
            group_id="dbt_models",
            project_config=ProjectConfig(
                dbt_project_path=f"{DBT_DIR}", # Onde está a pasta do dbt (definimos no docker-compose)
            ),
            profile_config=ProfileConfig(
                profile_name="transform_crypto",
                target_name="dev",
                # O Cosmos consegue ler as credenciais do PostgresHook do Airflow
                profile_mapping=PostgresUserPasswordProfileMapping(
                    conn_id="postgres_dw", 
                    profile_args={"schema": "public"}
                )
            ),
            render_config=RenderConfig(
                test_behavior=TestBehavior.AFTER_ALL # Corre os testes depois de todos os modelos terem corrido
            )
        )

    # --- 4. BLOCO DE SERVIÇO (Exportação CSV) ---
    with TaskGroup('4_Serve_Data') as serve_group:
        t_serve_csv = PythonOperator(
            task_id='serve_gold_to_csv', 
            python_callable=serve_gold_to_csv
        )
    

    # 🔗 DEFINIÇÃO DA ORDEM DE EXECUÇÃO
    extract_group >> load_group >> dbt_group >> serve_group