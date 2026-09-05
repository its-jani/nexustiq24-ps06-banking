#!/usr/bin/env bash
set -euo pipefail
# PS06 — canonical clean-machine run command. Idempotent; safe to re-run.

# 1. Create a virtualenv (idempotent) and install requirements into it.
PY=${PYTHON:-python3}
if [ ! -x ".venv/bin/python" ]; then
  "$PY" -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# 2. Load GEMINI_API_KEY from .env if present (never committed).
if [ -f ".env" ]; then
  set -a; . "./.env"; set +a
fi

# 3. Start the FastAPI server on all interfaces, port 8000.
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000