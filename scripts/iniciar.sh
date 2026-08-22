#!/usr/bin/env bash
# Sobe o Dashboard Executivo localmente (Linux/macOS).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Criando ambiente virtual..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

echo "Dashboard Executivo em http://127.0.0.1:8000"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
