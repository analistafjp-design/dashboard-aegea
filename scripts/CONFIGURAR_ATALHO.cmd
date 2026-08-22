@echo off
setlocal
chcp 65001 >nul
title Configurar atalho do Dashboard AEGEA

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0configurar_atalho.ps1"
set "CODIGO=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO%
