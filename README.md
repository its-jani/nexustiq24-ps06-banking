TRACK_ID=PS06

# PS06 — Banking Transaction Risk Investigation Assistant

NexusTiQ24 submission. A transaction-history investigator for a bank's fraud desk
that produces an **investigation report whose first finding is whether anything
needs attention at all** — and says so plainly when the history is clean.

## Demo video

[Watch the 5-minute demo](https://vimeo.com/1224273028?share=copy&fl=sv&fe=ci) — it walks through the
whole flow: starting the app, uploading a customer's transaction CSV, reading a
suspicious report (`NEEDS REVIEW`) with row-cited findings, and a routine report
(`CLEAN`) that correctly finds nothing.

## What it does

Upload a single customer's transaction history CSV (`date, description, payee,
amount, channel`). The app returns an investigation report whose **first finding is
the verdict**: `CLEAN` (nothing needs attention — said plainly) or `NEEDS REVIEW`
(with the exact transactions, the risk rules triggered, the deviation from this
customer's own behavior baseline, and what to look at first). It flags and explains;
it never asserts fraud — judgment stays with the investigator.

## How to run

From the repository root — one command to install, one command to start. This is the
only setup needed; no build step, no second terminal, nothing waits for a keypress.

```bash
pip install -r requirements.txt   # one-time install (~10 min)
python app.py                     # starts backend + frontend together on :8000
```

Open `http://localhost:8000`, upload a CSV, read the report. The web UI is served
directly by the Python app, so there is no separate frontend build or server.

Requires a Gemini API key: set the `GEMINI_API_KEY` environment variable (or copy
`.env.example` to `.env` and fill it in). The key is never committed. All LLM calls
use Gemini and all embeddings use `gemini-embedding-001` — Gemini is the only
external API.

`bash run.sh` also works on clean machines: it creates a virtualenv, installs the
requirements idempotently, then runs `python app.py`.

### Configuration (`.env`, all optional)

- `GEMINI_API_KEY` — required only for the Gemini narrative + similar-history lookup.
  Missing/expired key degrades gracefully to a deterministic narrative.
- `GEMINI_MODEL` — default `gemini-3.6-flash` (any flash/flash-lite class model).
- `REQUEST_TIMEOUT` — per-Gemini-call timeout seconds, default 50 (keeps every request under 60s).
- `MAX_TRANSACTIONS` — input row cap, default 10000.
- `MAX_UPLOAD_BYTES` — API upload cap, default 20 MB.

### API

- `GET  /health`                     → `{"status": "ok"}`
- `POST /investigate`                → multipart: `file=customer.csv` (field name `file`), form `customer_name`
- `GET  /investigate/{case_id}`      → an audited investigation by id

### CLI (no server)

```bash
python -m core.tools.cli data/sample_routine.csv
python -m core.tools.cli data/sample_suspicious.csv
```

### Tests

```bash
python -m pytest -q
```

## Data and documents

All data is generated for this problem — nothing is provided or downloaded:

- `data/sample_routine.csv` — ~26 weeks of a routine customer history (salary,
  groceries, utilities): the pipeline must return `CLEAN` with zero false positives.
- `data/sample_suspicious.csv` — the same rhythm plus a same-day cluster of large
  round-sum wire transfers to unknown payees: returns `NEEDS REVIEW` with every
  suspicious transaction cited by its exact input row.
- `core/tools/generate_data.py` — regenerates both fixtures:
  `python -m core.tools.generate_data --out out.csv` (routine) or with `--suspicious`.

## How it works

1. **ingest** — parse + validate the CSV, keeping the 1-based input row for traceability.
2. **baseline** — per-customer normal behavior: amount stats per direction, channel
   and payee distributions, inter-transaction timing.
3. **rules** — deterministic risk rules (large outlier, rapid sequence, round amounts,
   channel anomaly, large new payee, elevated frequency) firing only with citable rows.
4. **retriever** — local FAISS index over gemini-embedding-001 embeddings for
   similar-history context.
5. **reportgen** — Gemini writes the human narrative, strictly as a summary of the
   machine evidence. No key → deterministic verdict + findings still returned.

Every investigation is recorded in `data/audit.db` (case id, input fingerprint,
verdict, findings, narrative); the report is retrievable by case id via the API.
Clean histories stay clean: every rule is thresholded against the customer's own
baseline.

## Repo map

```
app.py                → single entry point: starts backend + frontend together on :8000
requirements.txt      → all Python dependencies (pip install -r requirements.txt)
README.md             → this file
core/                 → ingest · baseline · rules · retriever · reportgen · service · api
core/web/static/      → the web UI served by app.py (no separate frontend build)
data/                 → generated sample histories (routine + suspicious)
tests/                → pytest suite (one file per module)
SPEC.md / SUBMISSION.md / tasks/ → spec, tech notes, and build plan
docs/screenshots/     → UI screenshots
run.sh                → optional clean-machine runner (venv + pip + python app.py)
```

Tracked commit history is the plan in motion: one commit per vertical slice.
