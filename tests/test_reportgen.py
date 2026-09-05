from datetime import datetime

from core.baseline import compute_baseline
from core.models import RiskFinding, Transaction
from core.reportgen import build_prompt, generate_report, _fallback_narrative

ROUTINE = [
    Transaction(row=3, date=datetime(2024, 1, 5, 9, 0), description="Grocery", payee="Store",
                amount=-45.34, channel="card"),
    Transaction(row=4, date=datetime(2024, 1, 12, 9, 0), description="Grocery", payee="Store",
                amount=-52.10, channel="card"),
    Transaction(row=5, date=datetime(2024, 1, 19, 9, 0), description="Salary", payee="Acme",
                amount=2000.00, channel="direct_deposit"),
]

SUS = ROUTINE + [
    Transaction(row=6, date=datetime(2024, 1, 26, 9, 0), description="Wire", payee="Shell Ltd",
                amount=-9000.00, channel="wire"),
]

FINDINGS = [
    RiskFinding(rule_id="flat_outlier", severity="high", message="outflow -9000 exceeds normal range",
                rows=(6,), evidence="median=-48.72 threshold=-700.00"),
]


def test_fallback_narrative_clean_is_confident():
    baseline = compute_baseline(ROUTINE)
    text = _fallback_narrative("CLEAN", baseline, [], None, customer_name="Jane Doe")
    assert text.startswith("VERDICT: CLEAN")
    assert "clean" in text.lower() and "no further" in text.lower()
    assert "fraud" not in text.lower()


def test_fallback_narrative_cites_rows_and_leads_with_verdict():
    baseline = compute_baseline(SUS)
    text = _fallback_narrative("NEEDS REVIEW", baseline, FINDINGS, None, customer_name="Jane Doe")
    assert text.startswith("VERDICT: NEEDS REVIEW")
    assert "row(s) 6" in text
    assert "flat_outlier" in text
    assert "fraud" not in text.lower()


def test_generate_report_with_stub_llm():
    calls = []

    def stub(prompt):
        calls.append(prompt)
        return "VERDICT: NEEDS REVIEW\nCustom narrative."

    baseline = compute_baseline(SUS)
    text = generate_report("NEEDS REVIEW", baseline, FINDINGS, customer_name="J", llm_fn=stub)
    assert text == "VERDICT: NEEDS REVIEW\nCustom narrative."
    assert calls and "verdict" in calls[0].lower()


def test_generate_report_falls_back_without_key_or_stub():
    baseline = compute_baseline(ROUTINE)
    text = generate_report("CLEAN", baseline, [], customer_name="J", llm_fn=None, api_key=None)
    assert text.startswith("VERDICT: CLEAN")


def test_prompt_includes_instructions_and_data():
    baseline = compute_baseline(SUS)
    prompt = build_prompt("NEEDS REVIEW", baseline, FINDINGS, customer_name="Jane", model="x")
    assert "NEEDS REVIEW" in prompt
    assert "never" in prompt.lower() and "fraud" in prompt.lower()
    assert "rows=(6,)" in prompt and "flat_outlier" in prompt