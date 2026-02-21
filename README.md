# 🚀 Crypto DataOps Pipeline: End-to-End Analytics Engineering

![DataOps](https://img.shields.io/badge/Methodology-DataOps-blue)
![Airflow](https://img.shields.io/badge/Orchestrator-Airflow_2.8.1-017CEE?logo=apacheairflow)
![dbt](https://img.shields.io/badge/Transformation-dbt_core-FF694B?logo=dbt)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql)
![Docker](https://img.shields.io/badge/Infrastructure-Docker-2496ED?logo=docker)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=githubactions)

## 📌 Visão Geral do Projeto
Este projeto implementa uma arquitetura moderna de dados (Modern Data Stack) para extração, transformação e orquestração de métricas do mercado de criptomoedas (CoinGecko). Construído com uma mentalidade rigorosa de **DataOps**, o pipeline foca-se na escalabilidade, reprodutibilidade e isolamento de ambientes.

## 🏗️ Arquitetura e Fluxo de Dados (ETL/ELT)

1. **Extração (Python + Airflow):** Scripts em Python extraem dados da API e carregam-nos para o Data Lake (MinIO) e para a camada `raw` no PostgreSQL.
2. **Transformação (dbt):** - **Silver Layer (`staging`):** Limpeza e normalização dos dados (Materializados como `views`).
   - **Gold Layer (`marts`):** Criação de tabelas de factos e dimensões para reporting, como `fct_crypto_daily_metrics` (Materializados como `tables`).
   - *Nota:* Utilização de uma macro customizada (`generate_schema_name`) para garantir a escrita limpa nos schemas de destino, sem prefixos.
3. **Exportação:** Geração de um ficheiro `.csv` dinâmico isolado num volume local (`/exports`) para consumo seguro em ferramentas de BI (PowerBI).

## 🧠 Boas Práticas de DataOps Implementadas

- **Infraestrutura como Código (IaC):** Todo o ambiente é levantado via `docker-compose.yml` com mapeamento rigoroso de volumes.
- **Microserviços:** Airflow dividido em processos independentes (`Webserver` e `Scheduler`) para garantir resiliência e evitar falhas em cascata.
- **Dependency Pinning:** Ficheiro `requirements.txt` blindado (ex: `apache-airflow==2.8.1`) para evitar quebras por atualizações silenciosas (Dependency Hell).
- **Separação de Preocupações (SoC):** Código de orquestração (`dags/`) e código de transformação (`coingecko_dw/`) vivem em diretórios paralelos para otimizar o *parsing* do Airflow.
- **Integração Contínua (CI):** Pipeline configurado no GitHub Actions para levantar um Postgres efémero e validar a compilação do dbt (`dbt compile`) em cada *Push*/*Pull Request*.

## 📂 Estrutura do Repositório

```text
├── .github/workflows/      # Pipelines de CI/CD (GitHub Actions)
├── coingecko_dw/           # Projeto dbt (Transformação de Dados)
│   ├── models/
│   │   ├── staging/        # Modelos da camada Silver
│   │   └── marts/          # Modelos da camada Gold
│   └── macros/             # Macros Jinja (ex: custom schema names)
├── dags/                   # DAGs do Airflow (Orquestração e Python Scripts)
├── exports/                # Volume isolado com os outputs (CSVs) para o PowerBI
├── docker-compose.yml      # Infraestrutura (Postgres, MinIO, Airflow)
├── Dockerfile              # Imagem customizada do Airflow com dependências
├── Makefile                # Atalhos para comandos Docker e dbt
└── requirements.txt        # Dependências fixadas (Airflow, dbt, etc.)