from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Transaction:
    """A single, validated transaction.

    `row` preserves the 1-based CSV input line (header = 1) so every finding can
    point back to the exact input row it came from (hard rule 1).
    """

    row: int
    date: datetime
    description: str
    payee: str
    amount: float  # negative = outflow, positive = inflow
    channel: str


@dataclass(frozen=True)
class RiskFinding:
    """One machine-generated, traceable flag. Never asserts fraud."""

    rule_id: str
    severity: str  # low | medium | high
    message: str
    rows: tuple[int, ...]  # 1-based input rows involved
    evidence: str  # numbers backing the finding, readable by an investigator


@dataclass(frozen=True)
class Baseline:
    """Per-customer normal-behavior profile computed solely from the input history."""

    n: int
    span_days: float
    inflow: tuple[float, float, float, float, float] | None  # (mean, std, median, q1, q3)
    outflow: tuple[float, float, float, float, float] | None
    channels: dict[str, float]  # channel -> share of transactions
    payees: dict[str, int]  # payee -> count
    median_gap_hours: float  # median inter-transaction gap
    day_counts: list[int]  # transactions per day, chronological
    hour_histogram: dict[int, int]  # hour-of-day -> count


@dataclass(frozen=True)
class InvestigationReport:
    """Full investigation result. `verdict` is the FIRST finding."""

    verdict: str  # "CLEAN" | "NEEDS REVIEW"
    summary: str
    findings: list[RiskFinding] = field(default_factory=list)
    narrative: str = ""
    cited_transactions: list[Transaction] = field(default_factory=list)
    case_id: str = ""
    customer_name: str = ""