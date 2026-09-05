# Spec: PS06 — Banking Transaction Risk Investigation Assistant

## Capability Map

| Module id | Responsibility | Depends on |
|---|---|---|
| ingest | Parse + validate a customer's transaction CSV into standardized transactions | — |
| baseline | Per-customer normal-behavior statistics (amounts, channels, payees, timing) | ingest |
| rules | Deterministic risk-rule engine → traceable, evidence-cited findings | ingest, baseline |
| retriever | gemini-embedding-001 + local FAISS similar-history lookup | ingest |
| reportgen | Gemini narrative synthesis grounded in machine evidence (fallback-safe) | ingest, baseline, rules, retriever |
| service | Orchestrator: ingest → baseline → rules → retriever → reportgen; emit InvestigationReport | all above |
| api | FastAPI server, SQLite audit trail, single-page UI | service |

Build order: ingest → baseline → rules → retriever → reportgen → service → api.
Interfaces live at the boundaries recorded in this map; each module is independently testable.

## Objective

A bank's fraud desk uploads one customer's transaction history (date, description,
payee, amount, channel) covering several months. The system returns an investigation
report whose **first finding is whether anything needs attention at all**.

When suspicious activity is found the report must include:
1. The specific transactions involved and how they connect
2. Which exact risk rule was triggered
3. How the activity differs from this customer's normal behavior (baseline)
4. What an investigator should look at first

When nothing needs attention, the report must say so plainly and confidently.
A system that finds suspicion everywhere is as useless as one that finds none.

Operator persona: a single fraud investigator. Success = a correct, auditable,
human-readable report, produced from any arbitrary CSV in this schema.

## Hard Rules (never violate)

1. Every cited transaction MUST be traceable to the actual input data
2. The system MUST NEVER state that fraud has occurred
3. The system flags, explains, and hands judgment to the investigator
4. Uncertain cases escalate with context — they do not get decided
5. Normal histories must come back CLEAN — no false positives

## Tech Stack

- Python 3.11+ (any standard library)
- FastAPI + uvicorn (server)
- pandas + numpy (data processing)
- google-genai (Gemini API only; model flash / flash-lite)
- gemini-embedding-001 (embeddings only)
- FAISS (local vector store, no hosted DBs)
- sqlite3 (stdlib) for the audit trail
- python-dotenv (env loading)
- pytest (tests)

NO other external APIs. NO hosted vector databases. NO third-party RAG/memory services.
API key is read ONLY from env var `GEMINI_API_KEY` (via `.env` / dotenv). Never committed.

## Commands

```
Install:  python -m pip install -r requirements.txt   # one-time, ~10 min
Run:      python app.py                # one command: starts frontend + backend on :8000
          bash run.sh                  # installs deps (idempotent) then runs python app.py
API:      http://localhost:8000/                 (UI)
          POST /investigate                      (multipart: files=customer.csv, form: customer_name=...)
          GET  /investigate/{case_id}            (audited report by id)
          GET  /health
Test:     python -m pytest -q
Data:     python -m core.tools.generate_data --out data/sample_suspicious.csv (and --routine)
Direct:   python -m core.tools.cli data/sample_suspicious.csv
```

## Project Structure

```
app.py          → Single entry point: starts backend (FastAPI) + web UI together
core/           → Application source
  main.py         → FastAPI app, routes, web UI serving
  config.py       → Env config (GEMINI_API_KEY, GEMINI_MODEL, paths)
  models.py       → dataclasses: Transaction, RiskFinding, InvestigationReport
  ingest.py       → CSV parse + validation (module: ingest)
  baseline.py     → per-customer behavior baseline (module: baseline)
  rules.py        → deterministic risk rules (module: rules)
  retriever.py    → embeddings + FAISS similar-history lookup (module: retriever)
  reportgen.py    → Gemini narrative synthesis, fallback-safe (module: reportgen)
  service.py      → orchestrator (module: service)
  db.py           → SQLite audit trail (module: api)
  web/            → single-page UI assets
  tools/          → generate_data.py, cli.py (dev/eval utilities)
data/           → sample CSVs, audit.db (gitignored, runtime-generated)
tests/          → pytest suite, one file per module
tasks/          → plan.md + todo.md (graphify knows it; SKIP cascades)
SPEC.md         → this document
run.sh          → canonical clean-machine run command
requirements.txt
```

## Code Style

Python, PEP 8, type hints on all public signatures, protocol dataclasses for domain
shape, no comments unless they explain *why*. One snippet:

```python
@dataclass(frozen=True)
class Transaction:
    row: int            # 1-based CSV row, for traceability (hard rule 1)
    date: datetime
    description: str
    payee: str
    amount: float       # negative = outflow
    channel: str

@dataclass(frozen=True)
class RiskFinding:
    rule_id: str
    severity: str       # low | medium | high
    message: str
    rows: tuple[int, ...]   # traceable transaction row indexes
    evidence: str           # numbers supporting the finding
```

Naming: `snake_case` functions, modules match capability-map ids. No type-hint
overkill, no abstract base classes with one implementation.

## Testing Strategy

pytest, flat `tests/`, no fixtures framework ceremony (plain functions + small
helpers). Cover, at minimum:

- `test_ingest.py`    — valid parse, bad rows (missing/blank/invalid amount/unknown date), traceability of `row`
- `test_baseline.py`  — stats correctness on a hand-computed fixture
- `test_rules.py`     — each rule fires on a crafted fixture and stays silent on a routine one (no false positives)
- `test_service.py`   — routine CSV ⇒ verdict CLEAN, zero findings; crafted CSV ⇒ findings carry only real rows; report text never contains the word "fraud"
- `test_reportgen.py` — LLM stub injection: narrative built deterministically, fallback path when no API key

## Boundaries

- Always: validate input at the API boundary; test before commit; cite only real rows; run `.gitignore` hygiene (never stage `.env`, `data/*.db`, `graphify-out/`)
- Ask first: adding a dependency beyond the allowed list; changing the CSV schema; changing the run command
- Never: state fraud occurred; claim a rule fired without its transaction rows; commit `GEMINI_API_KEY` or `.env`; skip the CLEAN-case test

## Success Criteria

1. `bash run.sh` starts a server on a clean machine with zero manual steps (only `GEMINI_API_KEY` in env).
2. Routine history CSV → report opens with a CLEAN verdict and no findings (hard rule 5).
3. Crafted suspicious CSV → report opens with a NEEDS REVIEW verdict, names the exact rule(s),
   cites transaction rows present in the input, explains deviation from baseline,
   and tells the investigator what to look at first (hard rule 1, 3, 4).
4. Narrative produced by Gemini never asserts fraud; deterministic findings never do either (hard rule 2).
5. No API key → system still returns deterministic verdict + findings + a text summary (graceful degradation).
6. Every investigation recorded in SQLite (case id, input fingerprint, verdict, findings, report).

## Open Questions

- Judge-provided CSV schema may add columns (e.g. `transaction_id`, `balance`). Design
  tolerates extra columns; required columns are `date, description, payee, amount, channel`.
- Exact Gemini model name resolved at runtime from env `GEMINI_MODEL` (default `gemini-3.6-flash`);
  the SDK + test stubs make the model a knob, not a code fork.

## Assumptions

1. Amount sign encodes direction: negative = money out, positive = money in.
2. Date formats accepted: ISO `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`, and US `MM/DD/YYYY` (with/without time).
3. All transactions in one file belong to ONE customer — the baseline is computed from that same history.
4. An empty/blank `payee` field is allowed (bill payments, ATM); rules treat it as "no payee data".
5. "Several months" ≈ history span; no external account comparison is possible, so baseline is within-customer.