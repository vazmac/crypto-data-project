import os
import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook

# --- CONFIGURAÇÕES ---
PROJECT_DIR = os.getenv("AIRFLOW_HOME", "/opt/airflow")
DASHBOARD_DIR = f"{PROJECT_DIR}/dashboard_data"

# O nome do schema onde o dbt coloca as tabelas finais (gold)
SCHEMA_GOLD = "gold" 

# Garantir que a pasta existe
os.makedirs(DASHBOARD_DIR, exist_ok=True)

def serve_gold_to_csv(**context):
    execution_date = context['ds']
    
    print(f"🔌 A ligar à base de dados para inspecionar o schema '{SCHEMA_GOLD}'...")
    pg_hook = PostgresHook(postgres_conn_id='postgres_dw')
    engine = pg_hook.get_sqlalchemy_engine()
    
    # 1. Inspecionar o schema para obter os nomes das tabelas
    get_tables_query = f"""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = '{SCHEMA_GOLD}';
    """
    
    df_tables = pd.read_sql(get_tables_query, engine)
    tabelas_gold = df_tables['table_name'].tolist()
    
    if not tabelas_gold:
        print(f"⚠️ Nenhuma tabela encontrada no schema '{SCHEMA_GOLD}'.")
        return
        
    print(f"🔍 Encontradas {len(tabelas_gold)} tabelas para exportar: {tabelas_gold}")
    
    # 2. Exportação
    for tabela in tabelas_gold:
        print(f"📊 A extrair a tabela {tabela}...")
        
        # Query para ir buscar todos os dados da tabela atual
        query = f"SELECT * FROM {SCHEMA_GOLD}.{tabela};"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print(f"⚠️ A tabela {tabela} está vazia. A ignorar a criação do ficheiro...")
            continue
            
        # Geração do CSV
        filename = f"{tabela}_{execution_date}.csv"
        output_path = os.path.join(DASHBOARD_DIR, filename)
        
        df.to_csv(output_path, index=False)
        print(f"✅ Sucesso! {len(df)} linhas exportadas para: {output_path}")

    print("🎉 Exportação dinâmica de todo o schema concluída com sucesso!")