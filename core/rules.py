from dataclasses import dataclass
from datetime import timedelta
from statistics import median

from core.baseline import compute_baseline
from core.models import Baseline, RiskFinding, Transaction


@dataclass(frozen=True)
class Rule:
    """A deterministic, documented risk rule. Emits findings, never a verdict."""

    rule_id: str
    severity: str
    description: str
    fn: callable

    def __call__(self, txs, baseline):
        return self.fn(txs, baseline)


def _robust_threshold(values: list[float], k: float = 3.5) -> float:
    """High-confidence outlier threshold: median + max(k*MAD, IQR)."""
    m = median(values)
    mad = median(abs(v - m) for v in values) or 1.0
    s = sorted(values)
    iqr = s[int(0.75 * (len(s) - 1))] - s[int(0.25 * (len(s) - 1))]
    return m + max(k * mad * 1.4826, 1.5 * iqr)


def _flat_outlier(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    for positive in (True, False):
        vals = [t.amount for t in txs if (t.amount > 0) == positive]
        if len(vals) < 5:
            continue
        thr = _robust_threshold(vals)
        median_dir = median(vals)
        for t in txs:
            # Require BOTH a robust-statistical break AND a strong relative jump
            # (>=5x this customer's typical same-direction amount). A history with
            # legitimate broad categories (rent + groceries) must not self-flag.
            if (t.amount > 0) == positive and abs(t.amount) > thr \
                    and abs(t.amount) >= 5 * abs(median_dir):
                findings.append(RiskFinding(
                    rule_id="flat_outlier",
                    severity="high",
                    message=f"amount {'inflow' if positive else 'outflow'} of {t.amount:,.2f} "
                            f"far exceeds this customer's normal range (median {median_dir:,.2f}, "
                            f"robust threshold {thr:,.2f}).",
                    rows=(t.row,),
                    evidence=f"median={median_dir:,.2f} threshold={thr:,.2f} tx_row={t.row} amount={t.amount:,.2f}",
                ))
    return findings


def _rapid_sequence(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    window = timedelta(minutes=10)
    outflows = [t for t in txs if t.amount < 0]
    i, n = 0, len(outflows)
    while i < n:
        j = i + 1
        while j < n and (outflows[j].date - outflows[i].date) <= window:
            j += 1
        cluster = outflows[i:j]
        if len(cluster) >= 3 and (cluster[-1].date - cluster[0].date).total_seconds() <= 600:
            rows = tuple(t.row for t in cluster)
            findings.append(RiskFinding(
                rule_id="rapid_sequence",
                severity="high",
                message=f"{len(cluster)} outflows within {(cluster[-1].date - cluster[0].date).seconds or '60'}s "
                        f"({cluster[0].date:%Y-%m-%d %H:%M}). Multiple outbound transactions in a "
                        f"short window merit a first look.",
                rows=rows,
                evidence="rows=" + ",".join(map(str, rows)) +
                         f" span={(cluster[-1].date - cluster[0].date).total_seconds():.0f}s",
            ))
        i = j
    return findings


def _round_amount(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    for positive in (True, False):
        vals = [t.amount for t in txs if (t.amount > 0) == positive]
        if len(vals) < 3:
            continue
        median_dir = abs(median(vals))
        for t in txs:
            if (t.amount > 0) == positive and abs(t.amount) % 1000 == 0.0 and abs(t.amount) >= 1000 \
                    and abs(t.amount) >= 3 * median_dir:
                findings.append(RiskFinding(
                    rule_id="round_amount",
                    severity="medium",
                    message=f"round-sum amount of {t.amount:,.2f} at row {t.row}, atypical for this "
                            f"customer's typical {median_dir:,.0f} payment size.",
                    rows=(t.row,),
                    evidence=f"median={median_dir:,.2f} amount={t.amount:,.2f} row={t.row}",
                ))
    return findings


def _channel_anomaly(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    day = timedelta(hours=24)
    for channel, share in baseline.channels.items():
        if share >= 0.15:
            continue
        ch_out = sorted((t for t in txs if t.channel == channel and t.amount < 0), key=lambda t: t.date)
        i = 0
        while i < len(ch_out):
            burst = [ch_out[i]]
            j = i + 1
            while j < len(ch_out) and ch_out[j].date - ch_out[i].date <= day:
                burst.append(ch_out[j])
                j += 1
            if len(burst) >= 3:
                rows = tuple(t.row for t in burst)
                findings.append(RiskFinding(
                    rule_id="channel_anomaly",
                    severity="medium",
                    message=f"channel '{channel}' is uncommon for this customer ({share:.0%} of history) "
                            f"yet accounts for {len(burst)} outflows within 24h of {burst[0].date:%Y-%m-%d}.",
                    rows=rows,
                    evidence=f"channel={channel} share={share:.2f} rows=" + ",".join(map(str, rows)),
                ))
            i = j
    return findings


def _new_payee_large(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    counts = {p: c for p, c in baseline.payees.items()}
    out_vals = [t.amount for t in txs if t.amount < 0]
    if len(out_vals) < 3:
        return findings
    median_out = abs(median(out_vals))
    for t in txs:
        if t.amount < 0 and t.payee and counts.get(t.payee, 0) == 1 \
                and abs(t.amount) >= 3 * median_out and abs(t.amount) >= 500:
            findings.append(RiskFinding(
                rule_id="new_payee_large",
                severity="medium",
                message=f"one-time payment {t.amount:,.2f} to '{t.payee}' (seen only once) is "
                        f"{abs(t.amount) / median_out:.1f}x this customer's typical outgoing amount.",
                rows=(t.row,),
                evidence=f"payee={t.payee} amount={t.amount:,.2f} median_out={median_out:,.2f} row={t.row}",
            ))
    return findings


def _high_frequency(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    findings = []
    if not baseline.day_counts:
        return findings
    median_daily = median(baseline.day_counts)
    by_day: dict[str, list[int]] = {}
    for t in txs:
        by_day.setdefault(t.date.date().isoformat(), []).append(t.row)
    threshold = max(4, int(2 * median_daily))
    for day, rows in by_day.items():
        if len(rows) > threshold:
            findings.append(RiskFinding(
                rule_id="high_frequency",
                severity="medium",
                message=f"{len(rows)} transactions on {day}, well above this customer's typical "
                        f"{median_daily:.0f}/day.",
                rows=tuple(sorted(rows)),
                evidence=f"day={day} count={len(rows)} median_daily={median_daily:.0f} rows=" + ",".join(map(str, sorted(rows))),
            ))
    return findings


RULES: list[Rule] = [
    Rule("flat_outlier", "high", "A single transaction far outside the customer's normal amount range", _flat_outlier),
    Rule("rapid_sequence", "high", "Three or more outflows within a 10-minute window", _rapid_sequence),
    Rule("round_amount", "medium", "Large round-sum amount atypical for the customer's payment size", _round_amount),
    Rule("channel_anomaly", "medium", "Burst of activity on a channel rarely used by this customer", _channel_anomaly),
    Rule("new_payee_large", "medium", "Large payment to a payee seen only once", _new_payee_large),
    Rule("high_frequency", "medium", "A single day with far more transactions than the customer's norm", _high_frequency),
]


def run_rules(txs: list[Transaction], baseline: Baseline) -> list[RiskFinding]:
    """Run every rule. Deterministic; findings cite only real input rows."""
    return [f for rule in RULES for f in rule(txs, baseline)]