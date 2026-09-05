from datetime import datetime, timedelta
from math import isclose

from app.baseline import compute_baseline
from app.models import Transaction


def _tx(day, hour, amount, payee, channel):
    return Transaction(
        row=1,
        date=datetime(2024, 1, day, hour, 30),
        description="",
        payee=payee,
        amount=amount,
        channel=channel,
    )


def test_baseline_computes_split_amount_stats():
    history = [
        _tx(1, 9, 100.0, "Market", "card"),
        _tx(2, 9, 300.0, "Market", "card"),
        _tx(3, 9, 200.0, "Market", "card"),
        _tx(4, 9, -50.0, "Rent", "ach"),
        _tx(5, 9, -150.0, "Rent", "ach"),
    ]
    b = compute_baseline(history)
    assert b.n == 5
    inflow_mean, inflow_std, inflow_med, inflow_q1, inflow_q3 = b.inflow
    assert isclose(inflow_mean, 200.0)
    assert isclose(inflow_med, 200.0)
    out_mean, out_std, out_med, out_q1, out_q3 = b.outflow
    assert isclose(out_mean, -100.0)
    assert isclose(out_med, -100.0)


def test_baseline_handles_no_inflow_or_no_outflow():
    only_out = [_tx(1, 9, -10, "A", "card")] * 2
    b = compute_baseline(only_out)
    assert b.inflow is None
    assert b.outflow is not None
    only_in = [_tx(1, 9, 10, "A", "card")] * 2
    b = compute_baseline(only_in)
    assert b.outflow is None


def test_baseline_channel_and_payee_distribution():
    history = [
        _tx(1, 9, -10, "A", "card"),
        _tx(2, 9, -10, "A", "card"),
        _tx(3, 9, -10, "B", "ach"),
    ]
    b = compute_baseline(history)
    assert isclose(b.channels["card"], 2 / 3)
    assert isclose(b.channels["ach"], 1 / 3)
    assert b.payees["A"] == 2
    assert b.payees["B"] == 1


def test_baseline_timing_stats():
    history = [
        _tx(1, 9, -10, "A", "card"),
        _tx(1, 13, -10, "A", "card"),   # +4h
        _tx(1, 17, -10, "A", "card"),   # +4h
        _tx(2, 17, -10, "A", "card"),   # +24h
    ]
    b = compute_baseline(history)
    assert isclose(b.median_gap_hours, 4.0)
    assert b.day_counts == [3, 1]
    assert b.hour_histogram[9] == 1
    assert b.hour_histogram[13] == 1
    assert b.hour_histogram[17] == 2


def test_baseline_span_days():
    history = [
        _tx(1, 9, -10, "A", "card"),
        _tx(1, 9, -10, "A", "card"),
        Transaction(row=1, date=datetime(2024, 2, 9, 9, 30), description="", payee="A", amount=-10, channel="card"),
    ]
    assert isclose(compute_baseline(history).span_days, 39.0)