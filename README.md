# 🚀 Crypto DataOps Pipeline: End-to-End Analytics Engineering

![DataOps](https://img.shields.io/badge/Methodology-DataOps-blue)
![Python](https://img.shields.io/badge/Python-3.10-blue)
![Airflow](https://img.shields.io/badge/Orchestrator-Airflow_2.8.1-017CEE?logo=apacheairflow)
![dbt](https://img.shields.io/badge/Transformation-dbt_core-FF694B?logo=dbt)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql)
![MinIO](https://img.shields.io/badge/Data_Lake-MinIO-C7202C?logo=minio)
![Docker](https://img.shields.io/badge/Infrastructure-Docker-2496ED?logo=docker)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=githubactions)

## 📌 Visão Geral do Projeto
Este projeto é uma pipeline de dados **ELT (Extract, Load, Transform)** totalmente automatizada que cruza dados financeiros de criptomoedas com as suas respetivas métricas de sustentabilidade ambiental (ESG - Consumo de Energia e Pegada de Carbono). 

O objetivo é fornecer uma base de dados analítica limpa, testada e modelada num **Star Schema**, pronta para ser consumida por ferramentas de Business Intelligence (ex: Power BI) para analisar o impacto ambiental do mercado cripto.

## 🏗️ Arquitetura e Tecnologias

O projeto foi desenhado seguindo as melhores práticas da indústria (**Medallion Architecture** e **Infrastructure as Code**), utilizando uma stack moderna de dados:

* **Orquestração:** Apache Airflow (com Astronomer Cosmos)
* **Extração & APIs:** Python (`requests`, `pandas`) extraindo da CoinGecko API e Carbon Ratings API.
* **Data Lake (Storage):** MinIO (S3-compatible) para armazenamento de ficheiros brutos (JSON/CSV).
* **Data Warehouse:** PostgreSQL 17.
* **Transformação & Data Quality:** dbt (Data Build Tool).
* **Infraestrutura:** Docker & Docker Compose.

---

## ⚙️ O Pipeline de Dados

A DAG do Airflow está dividida em 4 fases lógicas utilizando `TaskGroups`:

1. **Extract (Data Lake):** * Extração diária das APIs com validação de schema e armazenamento seguro no MinIO (S3).
   * Atualização dinâmica da *Watchlist* de moedas ativas através de um MERGE (SCD Tipo 1).
2. **Load (Postgres Raw):** * Ingestão eficiente utilizando `StringIO` e `COPY EXPERT` em memória (Schema-on-Read), sem criar ficheiros físicos intermédios.
3. **Transform (dbt via Cosmos):** * Orquestração nativa dos modelos `.sql` do dbt diretamente no Airflow usando a biblioteca `astronomer-cosmos`.
   * **Silver Layer (Staging):** Limpeza de dados, tratamento de valores nulos (ex: conversão de `-1.0` da API) e desduplicação (`ROW_NUMBER()`).
   * **Gold Layer (Marts):** Criação de um Star Schema de alta performance com a `dim_crypto` e `fct_crypto_daily_metrics`.
   * **Testes de Qualidade:** Testes rigorosos de valores não-nulos, unicidade, Integridade Referencial (Foreign Keys) e regras de negócio.
4. **Serve (Exportação):** * Exportação orientada a metadados (Metadata-driven) que descobre as tabelas dinamicamente no schema `gold` e gera ficheiros `.csv` prontos para consumo no Power BI.

---

## 🌟 Destaques Técnicos

* **Idempotência:** O pipeline pode ser executado múltiplas vezes para a mesma data sem duplicar dados, garantindo a integridade do histórico.
* **Orquestração Granular (Cosmos):** Falhas na transformação são isoladas ao nível do modelo dbt, permitindo re-execuções cirúrgicas e dependências visuais perfeitas.
* **Gestão de Segredos:** Configuração de Connections (Postgres/MinIO) injetadas de forma automática no arranque do contentor através de Variáveis de Ambiente no `docker-compose.yml`.
* **Zero Hardcoding:** Os scripts de extração leem as tabelas da base de dados em tempo real para saber que moedas extrair, criando um ciclo dinâmico.

---

## 🚀 Como Executar Localmente

**Pré-requisitos:** Docker e Docker Compose instalados.

1. Clone este repositório:
   ```bash
   git clone [https://github.com/](https://github.com/)vazmac/crypto-data-project.git
   cd crypto-data-project

2. Crie um ficheiro .env na raiz com as suas credenciais e a sua API Key da CoinGecko.

3. Inicie a infraestrutura:
   ```bash
   make build
   make up

4. Aceda à UI do Airflow em http://localhost:8080 (admin / admin).

5. Ative a DAG crypto_daily_pipeline

---

## 📂 Estrutura do Repositório

```text
crypto_data_project/
├── dags/                           # DAGs e Scripts de Orquestração (Airflow)
│   ├── crypto_daily_pipeline.py    # DAG principal de ELT e serving
│   ├── scripts/                    # Scripts de extração, carregamento e serving
│   │   ├── extract_coingecko_market_data.py   # Extração de dados CoinGecko
│   │   ├── extract_esg_data.py                # Extração de dados ESG/Carbon
│   │   ├── load_coingecko_market_data.py      # Carregamento de dados CoinGecko em PostgreSQL
│   │   ├── load_esg_data.py                   # Carregamento de dados ESG em PostgreSQL
│   │   ├── serve_data.py                      # Exportação em CSV
│   │   ├── __init__.py
│   │   └── __pycache__/
│   ├── __pycache__/                # Cache Python compilado
│   └── logs/                       # Logs de execução dos DAGs
│
├── transform_crypto/               # Projeto dbt (Transformação & Data Quality)
│   ├── models/
│   │   ├── staging/                # Camada Silver (Limpeza e Desduplicação)
│   │   │   ├── stg_crypto_prices.sql
│   │   │   └── stg_carbon_metrics.sql
│   │   └── marts/                  # Camada Gold (Star Schema Analytics)
│   │       ├── dim_crypto.sql      # Dimensão de Criptomoedas
│   │       └── fct_crypto_daily_metrics.sql # Factos Diários
│   ├── macros/                     # Macros Jinja Personalizadas
│   ├── tests/                      # Testes de Qualidade de Dados
│   ├── seeds/                      # Dados estáticos (lookup tables)
│   ├── snapshots/                  # Histórico de mudanças (SCD Tipo 2)
│   ├── dbt_project.yml             # Configuração do projeto dbt
│   ├── profiles.yml                # Conexão com PostgreSQL
│   ├── logs/                       # Logs de execução dbt
│   └── README.md
│
├── scripts/                        # Scripts de Inicialização e Utilitários
│   └── init_db.sql                 # SQL para criação de schemas e tabelas raw
│
├── plugins/                        # Plugins Customizados do Airflow
│
├── dashboard_data/                 # Volume de Entrega (Exports em CSV)
│
├── logs/                           # Logs dos DAGs (ignorado no Git)
│   ├── dag_id=crypto_daily_pipeline/
│   ├── dag_id=extraction/
│   ├── dag_id=watchlist_load/
│   └── scheduler/
│
├── docker-compose.yml              # Infraestrutura IaC (Postgres, MinIO, Airflow, PGAdmin)
├── Dockerfile                      # Imagem Customizada para Airflow
├── Makefile                        # Automação de Comandos (build, up, down, logs, dbt)
├── requirements.txt                # Dependências Python (Airflow, dbt, libs)
├── servers.json                    # Configuração de Servidores (PGAdmin)
├── .gitignore                      # Ficheiros ignorados no versionamento
└── README.md                       # Documentação do Projeto