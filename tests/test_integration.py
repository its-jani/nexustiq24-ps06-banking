"""End-to-end guard: the shipped sample histories must behave exactly right.
sample_routine stays CLEAN (hard rule 5); sample_suspicious flags ONLY the
planted wires with real, traceable rows (hard rules 1, 3, 4)."""
from pathlib import Path

from core.service import investigate_csv

DATA = Path(__file__).resolve().parents[1] / "data"


def test_sample_routine_comes_back_clean():
    report = investigate_csv((DATA / "sample_routine.csv").read_text(encoding="utf-8"), api_key=None)
    assert report.verdict == "CLEAN"
    assert report.findings == []
    assert report.cited_transactions == []


def test_sample_suspicious_flags_only_planted_wires():
    report = investigate_csv((DATA / "sample_suspicious.csv").read_text(encoding="utf-8"), api_key=None)
    assert report.verdict == "NEEDS REVIEW"
    cited_rows = {t.row for t in report.cited_transactions}
    assert cited_rows == {106, 107, 108}  # exactly the three planted wires
    assert {f.rule_id for f in report.findings} >= {"flat_outlier"}
    assert "fraud" not in report.narrative.lower()


def test_sample_suspicious_row_106_is_the_wire():
    report = investigate_csv((DATA / "sample_suspicious.csv").read_text(encoding="utf-8"), api_key=None)
    txs = {t.row: t for t in report.cited_transactions}
    assert abs(txs[106].amount) == 15000.0
    assert txs[106].channel == "wire"