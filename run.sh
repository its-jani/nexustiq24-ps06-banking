#!/usr/bin/env bash
set -euo pipefail
# PS06 — canonical clean-machine run command. Idempotent; safe to re-run.
# Installs deps, then starts frontend + backend together: python app.py

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

# 2. GEMINI_API_KEY is loaded by core/config.py via python-dotenv from ./.env
#    (never committed). No shell sourcing needed — dotenv handles quoting.

# 3. Start everything with the single entry point: app.py (server + web UI).
exec "$VENV_PY" app.py