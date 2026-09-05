import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DATA_DIR / "audit.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS investigations (
            case_id TEXT PRIMARY KEY,
            customer_name TEXT,
            input_fingerprint TEXT,
            verdict TEXT,
            summary TEXT,
            narrative TEXT,
            findings_json TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def _insert(conn, row: dict):
    conn.execute(
        "INSERT INTO investigations (case_id, customer_name, input_fingerprint, verdict, summary, "
        "narrative, findings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            row["case_id"],
            row["customer_name"],
            row.get("input_fingerprint", ""),
            row["verdict"],
            row.get("summary", ""),
            row.get("narrative", ""),
            json.dumps(row.get("findings", [])),
            row.get("created_at", datetime.now(timezone.utc).isoformat()),
        ),
    )
    conn.commit()


def save_case(csv_text: str, report: dict, customer_name: str = "", db_path: Path | None = None) -> str:
    """Persist an investigation; returns its case id."""
    case_id = uuid.uuid4().hex[:16]
    fingerprint = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    conn = _connect(db_path)
    try:
        _insert(conn, {
            "case_id": case_id,
            "customer_name": customer_name,
            "input_fingerprint": fingerprint,
            "verdict": report["verdict"],
            "summary": report.get("summary", ""),
            "narrative": report.get("narrative", ""),
            "findings": report.get("findings", []),
        })
    finally:
        conn.close()
    return case_id


def get_case(case_id: str, db_path: Path | None = None) -> dict | None:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT case_id, customer_name, input_fingerprint, verdict, summary, narrative, "
            "findings_json, created_at FROM investigations WHERE case_id = ?",
            (case_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "case_id": row[0],
            "customer_name": row[1],
            "input_fingerprint": row[2],
            "verdict": row[3],
            "summary": row[4],
            "narrative": row[5],
            "findings": json.loads(row[6] or "[]"),
            "created_at": row[7],
        }
    finally:
        conn.close()