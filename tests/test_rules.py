from datetime import datetime, timedelta

from core.baseline import compute_baseline
from core.models import Transaction
from core.rules import RULES, run_rules

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)


def _tx(row, date, amount, payee, channel="card", description=""):
    return Transaction(row=row, date=date, description=description, payee=payee,
                       amount=amount, channel=channel)


def _routine_history(rows=None):
    """A normal customer: weekly salary, small choreographed outflows, one rent."""
    txs = []
    base = datetime(2024, 1, 1, 9, 0)
    n = rows or 60
    txs.append(_tx(1, base, 2500.0, "ACME Corp", "direct_deposit", "Salary"))
    r = 2
    for i in range(n):
        week = base + i * 7 * DAY
        txs += [
            _tx(r + 0, week + 0 * HOUR, -45.34, "Grocery Store"),
            _tx(r + 1, week + 2 * HOUR, -12.99, "Coffee Shop"),
            _tx(r + 2, week + 5 * HOUR, -1350.00, "Rent Co", "ach", "Rent"),
            _tx(r + 3, week + 26 * HOUR, -200.00, "Utility Co", "ach"),
        ]
        r += 4
    return txs


def _all_findings(txs):
    baseline = compute_baseline(txs)
    return [f for rule in RULES for f in rule(txs, baseline)]


def _ids(txs):
    return {f.rule_id for f in _all_findings(txs)}


def test_routine_history_produces_zero_findings():
    txs = _routine_history()
    assert _all_findings(txs) == []


def test_rent_amount_does_not_trigger_round_amount():
    """A large-but-regular 1350 rent must stay clean (baseline-anchored rule)."""
    txs = _routine_history(30)
    assert _ids(txs) == set()


def test_flat_outlier_fires_high():
    txs = _routine_history(20)
    big = txs[-1]
    txs.append(_tx(9999, big.date + 2 * DAY, -20000.0, "Unknown Ltd", "wire"))
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "flat_outlier"]
    assert hits and hits[0].severity == "high"
    assert 9999 in hits[0].rows


def test_rapid_sequence_fires():
    txs = _routine_history(20)
    txs.append(_tx(10, txs[-1].date + DAY, -250.0, "ATM", "atm"))
    last = txs[-1]
    cluster = [
        _tx(11, last.date + HOUR, -300.0, "Casino X", "atm"),
        _tx(12, last.date + HOUR + timedelta(minutes=2), -500.0, "Casino X", "atm"),
        _tx(13, last.date + HOUR + timedelta(minutes=4), -250.0, "Casino X", "atm"),
        _tx(14, last.date + HOUR + timedelta(minutes=6), -400.0, "Casino X", "atm"),
    ]
    txs.extend(cluster)
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "rapid_sequence"]
    assert hits
    assert set(hits[0].rows) == {11, 12, 13, 14}
    assert hits[0].severity == "high"


def test_channel_anomaly_fires_for_rare_channel_burst():
    txs = _routine_history(20)
    last = txs[-1].date
    wire = [
        _tx(30, last + timedelta(hours=2), -3000.0, "Shady Escrow", "wire"),
        _tx(31, last + timedelta(hours=5), -4000.0, "Shady Escrow", "wire"),
        _tx(32, last + timedelta(hours=9), -5000.0, "Shady Escrow", "wire"),
    ]
    txs.extend(wire)
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "channel_anomaly"]
    assert hits
    assert set(hits[0].rows) == {30, 31, 32}


def test_new_payee_large_fires():
    txs = _routine_history(20)
    txs.append(_tx(40, txs[-1].date + DAY, -8000.0, "Never Seen Corp", "wire"))
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "new_payee_large"]
    assert hits
    assert 40 in hits[0].rows


def test_round_amount_fires_only_when_anomalous():
    txs = _routine_history(20)
    txs.append(_tx(50, txs[-1].date + DAY, -10000.0, "Shell Holdings", "ach"))
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "round_amount"]
    assert hits
    assert 50 in hits[0].rows


def test_high_frequency_day_fires():
    txs = _routine_history(20)
    last = txs[-1].date
    burst = [_tx(60 + i, last + (i + 1) * HOUR, -150.0, "Money Mart", "atm") for i in range(8)]
    txs.extend(burst)
    baseline = compute_baseline(txs)
    hits = [f for f in run_rules(txs, baseline) if f.rule_id == "high_frequency"]
    assert hits
    assert len(hits[0].rows) >= 8


def test_every_finding_cites_existing_rows():
    txs = _routine_history(20)
    txs.append(_tx(77, txs[-1].date + DAY, -9000.0, "Shell Ltd", "wire"))
    baseline = compute_baseline(txs)
    all_rows = {t.row for t in txs}
    for f in run_rules(txs, baseline):
        for r in f.rows:
            assert r in all_rows, f"{f.rule_id} cites missing row {r}"


def test_rules_expose_ids_and_descriptions():
    assert RULES
    for rule in RULES:
        assert rule.rule_id
        assert rule.description
        assert rule.severity in ("low", "medium", "high")