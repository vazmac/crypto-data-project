# 🚀 Crypto DataOps Pipeline: End-to-End Analytics Engineering

![DataOps](https://img.shields.io/badge/Methodology-DataOps-blue)
![Airflow](https://img.shields.io/badge/Orchestrator-Airflow_2.8.1-017CEE?logo=apacheairflow)
![dbt](https://img.shields.io/badge/Transformation-dbt_core-FF694B?logo=dbt)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql)
![MinIO](https://img.shields.io/badge/Data_Lake-MinIO-C7202C?logo=minio)
![Docker](https://img.shields.io/badge/Infrastructure-Docker-2496ED?logo=docker)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=githubactions)

## 📌 Visão Geral do Projeto
Este projeto implementa uma arquitetura moderna de dados (Modern Data Stack) para extração, transformação e orquestração de métricas do mercado de criptomoedas (API CoinGecko). Desenhado com rigorosas práticas de **DataOps**, o pipeline foca-se em escalabilidade, reprodutibilidade, isolamento de recursos e CI/CD.

## 🏗️ Arquitetura e Fluxo de Dados (ELT)

1. **Extração (Python + Airflow):** Scripts extraem dados da API e carregam-nos para a *Landing Zone* no Data Lake (MinIO) e para o schema `raw` no PostgreSQL.
2. **Transformação (dbt):** - **Silver Layer (`staging`):** Limpeza, tipagem e normalização.
   - **Gold Layer (`marts`):** Criação de tabelas de factos prontas para negócio, como `fct_daily_metrics`.
3. **Distribuição:** Geração de ficheiros `.csv` agregados e isolados num volume local (`/dashboard_data`) para consumo direto em ferramentas de BI (PowerBI/Tableau), garantindo que a camada de visualização não sobrecarrega a base de dados transacional.

---

## 🧠 Decisões de Arquitetura

Num cenário corporativo, as escolhas tecnológicas devem equilibrar performance, custos e agilidade de desenvolvimento. Abaixo estão as justificações para o design desta infraestrutura:

### 1. MinIO em vez de AWS S3 / GCP Cloud Storage
**O Desafio:** Desenvolver localmente com serviços Cloud reais gera custos desnecessários e requer gestão complexa de credenciais de IAM.
**A Solução:** Utilização do MinIO via Docker. Sendo 100% compatível com a API do Amazon S3, permite desenvolver e testar scripts de extração em ambiente local (DEV). Quando o código transita para Produção na Cloud, basta alterar as variáveis de ambiente, sem refatorização de código.

### 2. GitHub Actions em vez de Kubernetes (K8s) para Separação de Ambientes
**O Desafio:** Manter uma verdadeira separação física entre DEV e PROD. Orquestrar isto localmente com K8s (Namespaces) exigiria recursos de hardware massivos (RAM/CPU), inviabilizando o desenvolvimento num computador pessoal.
**A Solução:** Assumir o Docker local como um ambiente puro de Desenvolvimento (DEV). A garantia de qualidade é feita através de **CI/CD com GitHub Actions**. A cada *Push*, o GitHub levanta um PostgreSQL efémero na cloud, instala o dbt, testa a compilação do SQL (`dbt compile` e `dbt test`) e destrói o ambiente. Isto garante isolamento total de testes sem custos de infraestrutura permanente.

### 3. Desacoplamento do Apache Airflow (Scheduler vs. Webserver)
**O Desafio:** Correr todos os processos do Airflow num único container (*monólito*) cria um *Single Point of Failure* (SPOF). Se a interface web consumir demasiada memória, pode derrubar o motor de agendamento.
**A Solução:** Separação do Airflow em dois microserviços no `docker-compose.yml`. O `airflow-scheduler` atua isoladamente como o motor crítico de orquestração, enquanto o `airflow-webserver` gere apenas a UI. Isto permite escalabilidade independente e limita o *blast radius* em caso de falha.

### 4. Gestão Rigorosa de Dependências (Dependency Pinning)
**O Desafio:** O "Inferno de Dependências" (Dependency Hell) no Python, onde pacotes atualizados silenciosamente quebram pipelines em Produção.
**A Solução:** Fixação estrita de versões no `requirements.txt` (ex: `apache-airflow==2.8.1`), garantindo que os *builds* do Docker são determinísticos e imunes a atualizações indesejadas de pacotes terceiros (ex: providers da Amazon).

---

## 📂 Estrutura do Repositório

```text
crypto_data_project/
├── .github/workflows/      # Pipeline de CI/CD (simulação de ambiente empresarial)
├── dags/                   # DAGs do Airflow e scripts de extração Python
│   ├── market_data_extraction.py  # Extração de dados de mercado
│   ├── serve_crypto.py             # Extração de dados maturados em formato CSV para enviar para a equipa responsável por PowerBI
│   ├── watchlist_load.py          # Lista fixa de cryptomoedas a analisar
│   └── logs/
├── transform_crypto/       # Projeto dbt (Transformação de Dados)
│   ├── models/
│   │   ├── staging/        # Modelos da camada Silver
│   │   └── marts/          # Modelos da camada Gold
│   ├── macros/             # Macros Jinja personalizadas
│   ├── tests/
│   ├── seeds/
│   ├── snapshots/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── logs/
├── scripts/                # Scripts de inicialização com criação de schema e tabelas raw necessárias
│   └── init_db.sql
├── plugins/                
├── dashboard_data/         # Volume isolado de entrega de dados (Exports em CSV)
│   └── crypto_dashboard_2026-02-21.csv
├── logs/                   # Logs dos DAGs executados
├── docker-compose.yml      # Infraestrutura IaC (Postgres, PGAdmin, MinIO, Airflow)
├── Dockerfile              # Imagem customizada de Airflow
├── Makefile                # Automação de comandos do ciclo de vida local
├── requirements.txt        # Dependências de ambiente
├── servers.json            # Configuração de servidor e db no PGAdmin
└── README.md               # Documentação do projeto