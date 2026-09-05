# PS06 — Banking Transaction Risk Investigation Assistant

NexusTiQ24 submission. A transaction-history investigator for a bank's fraud desk
that produces an **investigation report whose first finding is whether anything
needs attention at all** — and says so plainly when the history is clean.

## Run

On a clean machine with a `GEMINI_API_KEY` environment variable (or `.env`):

```bash
bash run.sh          # installs deps (idempotent, virtualenv) → serves http://0.0.0.0:8000
```

Open `http://localhost:8000` → upload a customer transaction CSV → read the report.

### API

- `GET  /health`                     → `{"status": "ok"}`
- `POST /investigate`                → multipart: `files=customer.csv`, form `customer_name`
- `GET  /investigate/{case_id}`      → an audited investigation by id

### CLI (no server)

```bash
python -m app.tools.cli data/sample_routine.csv
python -m app.tools.cli data/sample_suspicious.csv
```

### Tests

```bash
python -m pytest -q
```

## Input schema

Required columns: `date, description, payee, amount, channel`. Extra columns are
ignored. `amount` sign encodes direction (negative = money out). Blank payee allowed.
Common date formats: `YYYY-MM-DD[ HH:MM:SS]`, `MM/DD/YYYY[ HH:MM:SS]`.

## How it works

1. **ingest** — parse + validate the CSV, keeping the 1-based input row for traceability.
2. **baseline** — per-customer normal behavior: amount stats per direction, channel
   and payee distributions, inter-transaction timing.
3. **rules** — deterministic risk rules (large outlier, rapid sequence, round amounts,
   channel anomaly, large new payee, elevated frequency) firing only with citable rows.
4. **retriever** — local FAISS index over gemini-embedding-001 embeddings for
   similar-history context.
5. **reportgen** — Gemini (flash/flash-lite) writes the human narrative, strictly
   as a summary of the machine evidence. No key → deterministic verdict + findings
   still returned (graceful degradation).

The system **flags and explains; it never asserts fraud** — judgment stays with
the investigator. Clean histories stay clean: every rule is thresholded against
the customer's own baseline.

## Repo map

```
SPEC.md               → capability map + six-core-area spec
tasks/plan.md         → technical plan, slices, commit plan, risks
tasks/todo.md         → task list (acceptance criteria per task)
app/                  → ingest · baseline · rules · retriever · reportgen · service · api
tests/                → pytest suite (one file per module)
data/                 → sample routine & suspicious CSVs (runtime: audit.db)
run.sh                → canonical run command
```

Tracked commit history is the plan in motion: one commit per vertical slice.