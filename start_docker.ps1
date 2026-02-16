Write-Host "🚀 A iniciar o Projeto Crypto..." -ForegroundColor Cyan

# 1. Verificar se o Docker está instalado
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ ERRO CRÍTICO: O Docker não está instalado nesta máquina." -ForegroundColor Red
    Write-Host "👉 Por favor instala o Docker Desktop primeiro: https://www.docker.com/products/docker-desktop"
    exit 1
}

# 2. Verificar se o Motor (Daemon) está a correr
Write-Host "🔍 A verificar o estado do Docker Engine..." -NoNewline
$dockerIsRunning = $false

try {
    docker info > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerIsRunning = $true
        Write-Host " [ONLINE]" -ForegroundColor Green
    }
} catch {
    # Ignora erros, assume que está desligado
}

# 3. Se estiver desligado, tentar arrancar
if (-not $dockerIsRunning) {
    Write-Host " [OFFLINE]" -ForegroundColor Yellow
    Write-Host "🐳 O Docker está a dormir. A tentar acordar a baleia..." -ForegroundColor Yellow
    
    # Tenta encontrar o executável padrão do Docker Desktop
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    
    if (Test-Path $dockerPath) {
        Start-Process $dockerPath
    } else {
        Write-Host "❌ Não encontrei o Docker Desktop no caminho padrão." -ForegroundColor Red
        Write-Host "👉 Abre o Docker manualmente e tenta de novo."
        exit 1
    }

    # 4. Loop de Espera (Polling) até o Docker responder
    Write-Host "⏳ A aguardar que o motor arranque (isto pode demorar 1-2 minutos)..." -NoNewline
    $retries = 0
    while ($retries -lt 60) { # Tenta durante 60 segundos x 2 = 2 minutos
        Start-Sleep -Seconds 2
        docker info > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " [PRONTO!]" -ForegroundColor Green
            $dockerIsRunning = $true
            break
        }
        Write-Host "." -NoNewline
        $retries++
    }

    if (-not $dockerIsRunning) {
        Write-Host "`n❌ O Docker demorou demasiado a responder via CLI." -ForegroundColor Red
        exit 1
    }
}

# 5. Lançar a Infraestrutura
Write-Host "`n🏗️  A levantar os containers (Airflow + Postgres + Metabase)..." -ForegroundColor Cyan
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Sucesso!" -ForegroundColor Green
    Write-Host "   -> Airflow: http://localhost:8080"
    Write-Host "   -> Metabase: http://localhost:3000"
} else {
    Write-Host "`n❌ Algo correu mal no docker-compose." -ForegroundColor Red
}