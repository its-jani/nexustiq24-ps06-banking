import io
from datetime import datetime

from app.models import RiskFinding
from app.service import decide_verdict, investigate, investigate_csv
from tests.test_rules import _routine_history


def _csv_rows(rows):
    return "\n".join(["date,description,payee,amount,channel"] + rows)


def test_routine_history_returns_clean_verdict_no_findings():
    txs = _routine_history(20)
    report = investigate(txs, customer_name="Jane", api_key=None)
    assert report.verdict == "CLEAN"
    assert report.findings == []
    assert "fraud" not in (report.narrative + report.summary).lower()


def test_crafted_history_returns_needs_review_with_cited_rows():
    txs = _routine_history(20)
    txs.append(_make_tx(9999, txs[-1].date, -20000.0, "Unknown Ltd", "wire"))
    report = investigate(txs, api_key=None)
    assert report.verdict == "NEEDS REVIEW"
    cited = {t.row for t in report.cited_transactions}
    assert cited <= {t.row for t in txs}  # only input rows (hard rule 1)
    assert 9999 in cited
    for f in report.findings:
        for r in f.rows:
            assert r in cited


def test_verdict_logic():
    assert decide_verdict([]) == "CLEAN"
    r = RiskFinding(rule_id="x", severity="low", message="m", rows=(1,), evidence="e")
    assert decide_verdict([r]) == "CLEAN"
    r2 = RiskFinding(rule_id="x", severity="medium", message="m", rows=(1,), evidence="e")
    assert decide_verdict([r2]) == "NEEDS REVIEW"
    r3 = RiskFinding(rule_id="x", severity="high", message="m", rows=(1,), evidence="e")
    assert decide_verdict([r3]) == "NEEDS REVIEW"


def test_investigate_csv_from_text():
    csv_text = _csv_rows([
        "2024-01-05,Grocery,Store,-45.00,card",
        "2024-01-12,Grocery,Store,-52.00,card",
        "2024-01-19,Salary,Acme,2000.00,direct_deposit",
    ])
    report = investigate_csv(io.StringIO(csv_text), api_key=None)
    assert report.verdict == "CLEAN"
    assert report.cited_transactions == []


def test_investigate_uses_llm_stub_when_injected():
    txs = _routine_history(20)
    txs.append(_make_tx(777, txs[-1].date, -25000.0, "Shell Ltd", "wire"))

    def stub(prompt):
        return "LLM NARRATIVE: check row 777."

    report = investigate(txs, api_key=None, llm_fn=stub)
    assert report.narrative.startswith("LLM NARRATIVE")


def test_investigate_embeds_similar_context_into_prompt():
    txs = _routine_history(6)
    txs.append(_make_tx(50, txs[-1].date, -9000.0, "Wire Co", "wire"))
    seen = {}

    def embed(texts):
        import numpy as np
        return [np.array([1.0, 0.0, float(i % 3)]) for i in range(len(texts))]

    def stub(prompt):
        seen["p"] = prompt
        return "ok"

    investigate(txs, api_key=None, embed_fn=embed, llm_fn=stub)
    assert "similar" in seen.get("p", "").lower()
    assert "row 50" in seen.get("p", "")


def _make_tx(row, date, amount, payee, channel):
    from app.models import Transaction
    return Transaction(row=row, date=date, description="", payee=payee, amount=amount, channel=channel)


def test_full_suspicious_csv_on_stream():
    rows = [
        "2024-01-05,Grocery,Store,-45.00,card",
        "2024-01-12,Grocery,Store,-52.00,card",
        "2024-01-19,Salary,Acme,2000.00,direct_deposit",
        "2024-01-26,Grocery,Store,-48.00,card",
        "2024-02-02,Grocery,Store,-55.00,card",
        "2024-02-09,Salary,Acme,2000.00,direct_deposit",
        "2024-02-10,Wire,Shell Escrow,-12000.00,wire",
    ]
    report = investigate_csv(io.StringIO(_csv_rows(rows)), api_key=None)
    assert report.verdict == "NEEDS REVIEW"
    ids = {f.rule_id for f in report.findings}
    assert "flat_outlier" in ids or "new_payee_large" in ids
    assert "fraud" not in report.narrative.lower()