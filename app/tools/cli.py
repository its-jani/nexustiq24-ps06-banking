"""Run one CSV through the full investigation pipeline, end-to-end, without a server."""
import argparse
import json
import sys
from pathlib import Path

import app.config as config
from app.service import investigate_csv


def main():
    parser = argparse.ArgumentParser(description="Investigate a transaction CSV")
    parser.add_argument("csv", help="path to a transaction CSV")
    parser.add_argument("--name", default="", help="customer name")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of prose")
    args = parser.parse_args()

    try:
        text = Path(args.csv).read_text(encoding="utf-8")
    except OSError as e:
        parser.error(str(e))

    report = investigate_csv(text, customer_name=args.name,
                             api_key=config.API_KEY, model=config.MODEL)

    if args.json:
        print(json.dumps({
            "verdict": report.verdict,
            "summary": report.summary,
            "findings": [
                {"rule_id": f.rule_id, "severity": f.severity, "message": f.message,
                 "rows": list(f.rows), "evidence": f.evidence}
                for f in report.findings
            ],
            "cited_rows": [t.row for t in report.cited_transactions],
            "case_id": report.case_id,
        }, indent=2))
        return

    print(f"VERDICT: {report.verdict}")
    print(report.summary)
    print()
    for f in report.findings:
        print(f"- [{f.severity}] {f.rule_id} rows={f.rows}: {f.message} ({f.evidence})")
    print()
    print(report.narrative)


if __name__ == "__main__":
    sys.exit(main())