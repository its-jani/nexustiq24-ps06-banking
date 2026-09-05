import io

from app.baseline import compute_baseline
from app.ingest import parse_csv
from app.models import InvestigationReport, RiskFinding, Transaction
from app.reportgen import generate_report
from app.retriever import build_retriever
from app.rules import run_rules

_ORDER = {"high": 0, "medium": 1, "low": 2}


def decide_verdict(findings: list[RiskFinding]) -> str:
    """FIRST finding: does anything need attention? Medium/high flags escalate."""
    if any(f.severity in ("medium", "high") for f in findings):
        return "NEEDS REVIEW"
    return "CLEAN"


def _summary(verdict: str, findings: list[RiskFinding], baseline) -> str:
    if verdict == "CLEAN":
        return (
            f"No activity needs an investigator's attention. {baseline.n} transactions over "
            f"{baseline.span_days:.0f} days are consistent with this customer's own baseline."
        )
    top = sorted(findings, key=lambda f: _ORDER[f.severity])
    names = ", ".join(dict.fromkeys(f.rule_id for f in findings))
    rows = ", ".join(str(r) for r in sorted({r for f in findings for r in f.rows}))
    return (
        f"{len(findings)} flag(s) from rule(s) {names} on input row(s) {rows}. "
        f"Start with: {top[0].rule_id} (row {min(top[0].rows)}, severity {top[0].severity})."
    )


def investigate(
    txs: list[Transaction],
    customer_name: str = "",
    api_key: str | None = None,
    model: str = "gemini-3.6-flash",
    embed_fn=None,
    llm_fn=None,
) -> InvestigationReport:
    """Full investigation pipeline. Deterministic verdict + findings; narrative
    is Gemini-grounded, with a deterministic fallback when no key is available."""
    baseline = compute_baseline(txs)
    findings = run_rules(txs, baseline)
    verdict = decide_verdict(findings)

    similar_notes = ""
    try:
        retriever = build_retriever(txs, embed_fn=embed_fn, api_key=api_key)
        if findings:
            anchor = min(sorted(findings, key=lambda f: _ORDER[f.severity])[0].rows)
            anchor_tx = next(t for t in txs if t.row == anchor)
            sim = retriever.similar(anchor_tx, k=3)
            if sim:
                parts = [f"row {t.row} ({abs(t.amount):,.0f}, {t.payee or t.channel})" for t, _ in sim]
                similar_notes = f"row {anchor} is closest to: " + ", ".join(parts)
    except Exception:
        pass  # embeddings are a luxury for the narrative; never block the verdict

    narrative = generate_report(
        verdict, baseline, findings, customer_name, llm_fn, api_key, model,
        similar_notes=similar_notes,
    )

    by_row = {t.row: t for t in txs}
    cited = {r: by_row[r] for f in findings for r in f.rows}
    cited_transactions = sorted(cited.values(), key=lambda t: t.row)

    return InvestigationReport(
        verdict=verdict,
        summary=_summary(verdict, findings, baseline),
        findings=findings,
        narrative=narrative,
        cited_transactions=cited_transactions,
        customer_name=customer_name,
    )


def investigate_csv(
    source: io.IOBase | str,
    customer_name: str = "",
    api_key: str | None = None,
    model: str = "gemini-3.6-flash",
    embed_fn=None,
    llm_fn=None,
) -> InvestigationReport:
    return investigate(parse_csv(source), customer_name, api_key, model, embed_fn, llm_fn)
