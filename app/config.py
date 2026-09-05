import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY / GEMINI_MODEL from .env if present

API_KEY: str | None = os.getenv("GEMINI_API_KEY") or None
MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", "20_000_000"))
MAX_TRANSACTIONS: int = int(os.getenv("MAX_TRANSACTIONS", "10000"))
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))