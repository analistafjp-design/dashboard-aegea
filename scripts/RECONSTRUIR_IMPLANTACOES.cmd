@echo off
setlocal
chcp 65001 >nul
title Reconstruir Implantacoes do Dashboard AEGEA

if "%~1"=="" (
    echo ERRO: informe o caminho completo da pasta Interior.
    echo Exemplo: scripts\RECONSTRUIR_IMPLANTACOES.cmd "C:\caminho\Interior"
    pause
    exit /b 1
)

cd /d "%~dp0.."
echo ============================================================
echo       RECONSTRUIR IMPLANTACOES DO DASHBOARD AEGEA
echo ============================================================
echo.
echo Somente os registros de implantacao serao substituidos.
echo.

".venv\Scripts\python.exe" "scripts\reconstruir_implantacoes.py" --pasta-interior "%~1"
set "CODIGO=%ERRORLEVEL%"

if not "%CODIGO%"=="0" (
    echo.
    echo A reconstrucao terminou com erro. O dashboard nao foi aberto.
    pause
    exit /b %CODIGO%
)

echo.
echo Abrindo o dashboard atualizado...
start "" "http://127.0.0.1:8000/"
pause
exit /b 0
