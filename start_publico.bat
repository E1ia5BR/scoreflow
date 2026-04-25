@echo off
echo ===================================================
echo Iniciando o ScoreFlow com Acesso Externo (Cloudflare)
echo ===================================================

echo.
echo Passo 1: Verificando cloudflared...
cloudflared --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] cloudflared nao encontrado no PATH. 
    echo Por favor, feche este terminal e abra um novo, pois o cloudflared acabou de ser instalado.
    pause
    exit /b
)

echo.
echo Passo 2: Iniciando o Backend (Docker Compose)
echo (Isso vai rodar Redis, Celery, FastAPI, e os Workers de IA)
start "Backend" cmd /c "docker-compose up && pause"

echo.
echo Passo 3: Iniciando o Frontend (Vite) na porta 5173
cd frontend
start "Frontend" cmd /c "npm run dev && pause"
cd ..

echo.
echo Aguardando 5 segundos para os servidores iniciarem...
timeout /t 5 >nul

echo.
echo Passo 4: Iniciando o Tunel Cloudflare para a porta 5173...
echo.
echo ===================================================
echo O Cloudflare vai abrir em uma nova janela!
echo Procure pelo link que termina em ".trycloudflare.com"
echo Copie e mande esse link para seus testadores!
echo ===================================================
echo.
pause
start "Cloudflare Tunnel" cmd /c "cloudflared tunnel --url http://localhost:5173 && pause"
