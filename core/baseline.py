from statistics import median

from core.models import Baseline, Transaction


def _quantiles(values: list[float]) -> tuple[float, float, float, float, float]:
    """Return (mean, std, median, q1, q3) for a list of amounts."""
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
    std = variance**0.5
    s = sorted(values)
    def q(p):
        i = (n - 1) * p
        lo, hi = int(i), min(int(i) + 1, n - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)
    return mean, std, median(s), q(0.25), q(0.75)


def compute_baseline(history: list[Transaction]) -> Baseline:
    """Per-customer normal-behavior profile, computed only from this history."""
    inflows = [t.amount for t in history if t.amount > 0]
    outflows = [t.amount for t in history if t.amount < 0]

    channels: dict[str, int] = {}
    payees: dict[str, int] = {}
    hour_histogram: dict[int, int] = {}
    for t in history:
        channels[t.channel] = channels.get(t.channel, 0) + 1
        if t.payee:
            payees[t.payee] = payees.get(t.payee, 0) + 1
        hour_histogram[t.date.hour] = hour_histogram.get(t.date.hour, 0) + 1

    if history:
        total = len(history)
        channels = {k: v / total for k, v in channels.items()}
    else:
        channels = {}

    gaps = [b.date - a.date for a, b in zip(history, history[1:]) if b.date > a.date]
    median_gap_hours = median(g.total_seconds() / 3600.0 for g in gaps) if gaps else 0.0

    by_day: dict[str, int] = {}
    first, last = history[0], history[-1]
    for t in history:
        by_day[t.date.date().isoformat()] = by_day.get(t.date.date().isoformat(), 0) + 1

    return Baseline(
        n=len(history),
        span_days=(last.date - first.date).total_seconds() / 86400.0,
        inflow=_quantiles(inflows) if inflows else None,
        outflow=_quantiles(outflows) if outflows else None,
        channels=channels,
        payees=payees,
        median_gap_hours=median_gap_hours,
        day_counts=sorted(by_day.values(), reverse=True),
        hour_histogram=hour_histogram,
    )