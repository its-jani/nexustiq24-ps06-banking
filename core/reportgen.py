from collections.abc import Callable

from core.config import REQUEST_TIMEOUT
from core.models import Baseline, RiskFinding

_SAFE_GUARD = (
    "You are writing for a bank fraud investigator. Hard constraints:\n"
    "1. NEVER state or imply that fraud has occurred or that any transaction is fraudulent. "
    "You flag behavior and hand the judgment to the investigator.\n"
    "2. Only cite transaction rows that appear in the evidence below (row N references the "
    "exact CSV input line).\n"
    "3. If the verdict is CLEAN, say so plainly and confidently in 2-3 sentences.\n"
    "4. If NEEDS REVIEW, first say what the investigator should look at FIRST, then explain "
    "each flagged row/rule and how it differs from this customer's baseline.\n"
    "5. Do not invent numbers that are not in the evidence.\n"
)


def build_prompt(
    verdict: str,
    baseline: Baseline,
    findings: list[RiskFinding],
    customer_name: str = "",
    model: str = "gemini-3.6-flash",
    similar_notes: str = "",
) -> str:
    """Assemble the grounded evidence package for the model. Findings are fact."""
    baseline_txt = (
        f"Customer baseline (from this history): {baseline.n} transactions over "
        f"{baseline.span_days:.0f} days; median gap {baseline.median_gap_hours:.1f}h; "
        f"channels {baseline.channels}; payees {baseline.payees}."
    )
    evidence_txt = "\n".join(
        f"- [{f.severity}] rule {f.rule_id} rows={f.rows} :: {f.evidence} :: {f.message}"
        for f in findings
    ) or "(none â€” history is routine)"
    similar_txt = similar_notes or "(embedding-based similar-history lookup unavailable)"
    return "\n".join([
        _SAFE_GUARD,
        f"Verifier's verdict (deterministic, do not contradict): {verdict}",
        f"Customer: {customer_name or 'unknown'}",
        baseline_txt,
        "Machine findings:",
        evidence_txt,
        "Similar historical activity for the flagged rows:",
        similar_txt,
        "",
        "Write the investigation report now.",
    ])


def _fallback_narrative(
    verdict: str,
    baseline: Baseline,
    findings: list[RiskFinding],
    similar: dict[int, list[tuple]] | None,
    customer_name: str = "",
) -> str:
    """Deterministic narrative: keeps the system fully functional without an API key."""
    lines = [f"VERDICT: {verdict}"]
    if verdict == "CLEAN":
        lines.append(
            f"This customer's history ({baseline.n} transactions over {baseline.span_days:.0f} "
            f"days) shows no behavior that needs an investigator's attention. All activity is "
            "consistent with this customer's own established baseline. No further review "
            "is required."
        )
    else:
        ranked = sorted(findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity])
        first = ranked[0]
        lines.append(
            f"Start here: rule {first.rule_id} (row(s) {', '.join(map(str, first.rows))}, "
            f"severity {first.severity}) â€” {first.message}"
        )
        for f in ranked:
            rows = ", ".join(map(str, f.rows))
            lines.append(f"- rule {f.rule_id} [{f.severity}], row(s) {rows}: {f.evidence}.")
        lines.append(
            "These are flags for investigation, not conclusions. An investigator should "
            "verify the transactions above against source records and the customer's context."
        )
    return "\n".join(lines)


def generate_report(
    verdict: str,
    baseline: Baseline,
    findings: list[RiskFinding],
    customer_name: str = "",
    llm_fn: Callable[[str], str] | None = None,
    api_key: str | None = None,
    model: str = "gemini-3.6-flash",
    similar_notes: str = "",
) -> str:
    """Produce the narrative. Uses the injected fn (test seam), then the Gemini API,
    then the deterministic fallback. The verdict/findings are always authoritative."""
    prompt = build_prompt(verdict, baseline, findings, customer_name, model, similar_notes)
    if llm_fn is not None:
        try:
            return str(llm_fn(prompt))
        except Exception:
            pass  # degrade to fallback rather than fail the investigation
    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT),
            )
            resp = client.chats.create(model=model).send_message(prompt)
            if resp.text:
                return resp.text
        except Exception:
            pass  # network/key errors degrade, never abort the report
    return _fallback_narrative(verdict, baseline, findings, None, customer_name)