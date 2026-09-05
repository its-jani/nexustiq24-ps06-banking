from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import app.config as config
import app.db as db
from app.ingest import IngestionError
from app.models import InvestigationReport
from app.service import investigate_csv

app = FastAPI(title="PS06 Banking Transaction Risk Investigation Assistant")
WEB_DIR = Path(__file__).parent / "web" / "static"


def report_to_dict(report: InvestigationReport) -> dict:
    return {
        "verdict": report.verdict,
        "summary": report.summary,
        "narrative": report.narrative,
        "customer_name": report.customer_name,
        "findings": [
            {"rule_id": f.rule_id, "severity": f.severity, "message": f.message,
             "rows": list(f.rows), "evidence": f.evidence}
            for f in report.findings
        ],
        "cited_transactions": [
            {"row": t.row, "date": t.date.isoformat(), "description": t.description,
             "payee": t.payee, "amount": t.amount, "channel": t.channel}
            for t in report.cited_transactions
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/investigate")
def investigate(file: UploadFile = File(...), customer_name: str = Form("")):
    raw = file.file.read()
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded CSV.")
    try:
        report = investigate_csv(
            text, customer_name=customer_name, api_key=config.API_KEY, model=config.MODEL
        )
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Investigation failed.")

    result = report_to_dict(report)
    try:
        result["case_id"] = db.save_case(text, result, customer_name)
    except Exception:
        result["case_id"] = ""  # audit is best-effort; never eat the report
    return result


@app.get("/investigate/{case_id}")
def get_investigation(case_id: str):
    case = db.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case