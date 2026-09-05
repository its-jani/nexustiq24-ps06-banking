"""Synthetic transaction histories for evaluation and demos.

Routine: salary + grocery + utility + rent rhythm, weekly, over ~6 months.
Suspicious: the same clean rhythm, then a same-day wire cluster to an unknown
payee and a very large round-sum withdrawal.
"""
import argparse
import random
from datetime import datetime, timedelta

PAYEES_RETAIL = ["Whole Foods", "Trader Joe's", "Safeway", "Coffee Bean", "Starbucks"]
PAYEES_UTIL = ["City Power", "City Water", "ISP Fiber", "MobileOne"]
SUSPICIOUS_PAYEES = ["Meridian Escrow Ltd", "Brightstone Trading", "Rivendell Holdings"]


def _shop_amount(rng: random.Random, n: int) -> float:
    return -round(rng.gauss(45, 6) + n % 3, 2)


def _salary(week: int) -> float:
    base = 2400.0 + (week % 4) * 12.0
    return round(base, 2)


def routine_csv(weeks: int = 26, seed: int = 7) -> str:
    rng = random.Random(seed)
    rows = ["date,description,payee,amount,channel"]
    start = datetime(2024, 1, 2, 9, 0)
    row = 2
    for w in range(weeks):
        base = start + w * timedelta(days=7)
        # Fridays: small groceries; Saturdays: utilities; Mondays: salary.
        d = base
        rows.append(f"{d:%Y-%m-%d %H:%M},Groceries,{PAYEES_RETAIL[rng.randrange(len(PAYEES_RETAIL))]},{_shop_amount(rng, w):.2f},card")
        row += 1
        d = base + timedelta(days=1)
        rows.append(f"{d:%Y-%m-%d %H:%M},Groceries,{PAYEES_RETAIL[rng.randrange(len(PAYEES_RETAIL))]},{_shop_amount(rng, w):.2f},card")
        row += 1
        d = base + timedelta(days=2)
        rows.append(f"{d:%Y-%m-%d %H:%M},Utilities,{PAYEES_UTIL[rng.randrange(len(PAYEES_UTIL))]},{-round(rng.uniform(60, 220), 2):.2f},ach")
        row += 1
        d = base + timedelta(days=3)
        rows.append(f"{d:%Y-%m-%d %H:%M},Salary,ACME Manufacturing,{_salary(w)},direct_deposit")
        row += 1
    return "\n".join(rows) + "\n"


def suspicious_csv(weeks: int = 26, seed: int = 7) -> str:
    rng = random.Random(seed)
    rows = routine_csv(weeks, seed).splitlines()
    last = datetime.strptime(rows[-2].split(",")[0], "%Y-%m-%d %H:%M")
    last += timedelta(days=3)
    rows += [
        f"{(last + timedelta(hours=1)):%Y-%m-%d %H:%M},Wire,{SUSPICIOUS_PAYEES[0]},-15000.00,wire",
        f"{(last + timedelta(hours=2)):%Y-%m-%d %H:%M},Wire,{SUSPICIOUS_PAYEES[1]},-12000.00,wire",
        f"{(last + timedelta(hours=3)):%Y-%m-%d %H:%M},Cash,{SUSPICIOUS_PAYEES[2]},-25000.00,cash",
    ]
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic PS06 transaction CSVs")
    parser.add_argument("--out", required=True, help="output CSV path")
    parser.add_argument("--suspicious", action="store_true", help="include suspicious activity")
    parser.add_argument("--weeks", type=int, default=26)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    content = suspicious_csv(args.weeks, args.seed) if args.suspicious else routine_csv(args.weeks, args.seed)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"wrote {args.out} ({len(content.splitlines()) - 1} transactions, "
          f"{'suspicious' if args.suspicious else 'routine'})")


if __name__ == "__main__":
    main()