@echo off
REM Sobe o Dashboard Executivo localmente (Windows).
cd /d "%~dp0.."

if not exist ".venv" (
  echo Criando ambiente virtual...
  python -m venv .venv
  .venv\Scripts\pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)

echo Dashboard Executivo em http://127.0.0.1:8000
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
