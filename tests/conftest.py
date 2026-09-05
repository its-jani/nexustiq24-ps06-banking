import sys
from pathlib import Path

import app.config as config
import app.db as db

# Tests must never call live Gemini/embedding APIs: force the no-key path.
config.API_KEY = None
config.MODEL = "test-model"

# Isolate the audit DB per test session.
config.DATA_DIR = Path(__file__).parent / "tmp_db"
db.DATA_DIR = config.DATA_DIR

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))