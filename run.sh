#!/usr/bin/env bash
set -euo pipefail
# PS06 — canonical clean-machine run command. Idempotent; safe to re-run.

# 1. Create a virtualenv (idempotent) and install requirements into it.
#    Cross-platform: works on Linux/macOS (bin/) and Windows git-bash (Scripts/).
PY=${PYTHON:-$(command -v python3 || command -v python)}
if [ ! -x ".venv/bin/python" ] && [ ! -x ".venv/Scripts/python.exe" ]; then
  "$PY" -m venv .venv
fi
if [ -x ".venv/bin/python" ]; then
  VENV_PY=".venv/bin/python"
else
  VENV_PY=".venv/Scripts/python.exe"
fi
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements.txt

# 2. GEMINI_API_KEY is loaded by app/config.py via python-dotenv from ./.env
#    (never committed). No shell sourcing needed — dotenv handles quoting.

# 3. Start the FastAPI server on all interfaces, port 8000.
exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000