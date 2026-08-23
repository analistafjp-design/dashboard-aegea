@echo off
setlocal
chcp 65001 >nul
title Atualizar Dashboard AEGEA

echo ============================================================
echo           ATUALIZAR DASHBOARD AEGEA
echo ============================================================
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0executar_atualizacao_manual.ps1"
set "CODIGO=%ERRORLEVEL%"

echo.
if "%CODIGO%"=="0" (
    echo Atualizacao local concluida. Pressione uma tecla para fechar.
) else (
    echo A atualizacao terminou com problema ^(codigo %CODIGO%^).
    echo Consulte a mensagem acima e a pasta data\logs.
)
pause >nul
exit /b %CODIGO%
