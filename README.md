TRACK_ID=PS06

<!-- TRACK_ID must stay the very first line: automated graders parse it. -->

# PS06 — Banking Transaction Risk Investigation Assistant

<!-- The one-paragraph pitch. Every fork of this repo starts here. -->
NexusTiQ24 submission. Upload one customer's transaction history and get an
investigation report whose **first finding is whether anything needs attention at
all** — ever. A system that flags everything is as useless as one that flags
nothing, so a routine history comes back `CLEAN` and says so plainly; a suspicious
one comes back `NEEDS REVIEW` with every claim anchored to a cited input row. It
flags and explains — it never asserts fraud. Judgment stays with the investigator.

## Demo video

[Watch the 5-minute demo](https://vimeo.com/1224273028?share=copy&fl=sv&fe=ci) — it walks through the
whole flow: starting the app, uploading a customer's transaction CSV, reading a
suspicious report (`NEEDS REVIEW`) with row-cited findings, and a routine report
(`CLEAN`) that correctly finds nothing.

## Quick start

The shortest path from clone to report. Three steps, no build step, no second terminal.

```bash
pip install -r requirements.txt                    # 1. install deps (one-time)
# 2. set your Gemini key: export GEMINI_API_KEY=...  (or copy .env.example to .env)
python app.py                                      # 3. start backend + UI together on :8000
```

Open `http://localhost:8000`, upload a CSV, read the report. The web UI is served
directly by the Python app — there is no separate frontend build or server.

`bash run.sh` is the equivalent one-shot for clean machines: it creates a
virtualenv, installs the requirements idempotently, then runs `python app.py`.
Either path is fine; the app behaves identically.

Requires a Gemini API key: set the `GEMINI_API_KEY` environment variable (or copy
`.env.example` to `.env` and fill it in). The key is never committed. Gemini is the
only external API — all LLM calls use Gemini and all embeddings use
`gemini-embedding-001`.

## Input format

A single CSV with these columns, in this order (a 1-based row number is kept
throughout so every finding can cite the exact input line):

```csv
date,description,payee,amount,channel
2024-01-02 09:00,Groceries,Safeway,-50.69,card
2024-01-03 09:00,Groceries,Whole Foods,-43.07,card
```

- `date` — `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`
- `amount` — negative = money out, positive = money in
- `channel` — e.g. `card`, `transfer`, `cash`, `online`

Run it on the included samples to see both report shapes:

```bash
python -m core.tools.cli data/sample_routine.csv      # → CLEAN (zero false positives)
python -m core.tools.cli data/sample_suspicious.csv   # → NEEDS REVIEW (row-cited)
```

## How it works

One pipeline, five stages. Each stage is a module under `core/` and worth reading
in this order:

1. **ingest** — parse + validate the CSV, keep the 1-based input row for traceability.
2. **baseline** — per-customer normal behavior: amount stats per direction, channel
   and payee distributions, inter-transaction timing.
3. **rules** — deterministic risk rules (large outlier, rapid sequence, round amounts,
   channel anomaly, large new payee, elevated frequency). Rules fire only when a
   citable row exists — no rules, no suspicion.
4. **retriever** — local FAISS index over `gemini-embedding-001` embeddings to pull
   in similar-history context for the narrative.
5. **reportgen** — Gemini writes the human narrative as a strict summary of the
   machine evidence. No key → a deterministic verdict + findings are still returned.

Every investigation is recorded in `data/audit.db` (case id, input fingerprint,
verdict, findings, narrative) and is retrievable by case id via the API.

<!-- Kept rules deterministic and event-driven on purpose: they keep CLEAN histories
     clean and make every NEEDS REVIEW claim traceable to evidence. -->

## Configuration (`.env`, all optional)

| Variable            | Default                | Meaning                                             |
| ------------------- | ---------------------- | --------------------------------------------------- |
| `GEMINI_API_KEY`    | *none*                 | Required for the narrative + similar-history lookup. Missing/expired key degrades gracefully to deterministic output. |
| `GEMINI_MODEL`      | `gemini-3.6-flash`     | Any flash / flash-lite class model.                 |
| `REQUEST_TIMEOUT`   | `50` (seconds)         | Per-Gemini-call timeout, keeps every request under 60s. |
| `MAX_TRANSACTIONS`  | `10000`                | Input row cap.                                      |
| `MAX_UPLOAD_BYTES`  | `20971520` (20 MB)     | API upload cap.                                     |

## API

| Method | Path                   | Purpose                                    |
| ------ | ---------------------- | ------------------------------------------ |
| `GET`  | `/health`              | Liveness → `{"status": "ok"}`              |
| `POST` | `/investigate`         | Multipart upload: `file` = CSV, `customer_name` = form field |
| `GET`  | `/investigate/{id}`    | Fetch an audited investigation by case id   |

## Tests

```bash
python -m pytest -q
```

The suite is one file per module under `tests/`. The knock-out case is the routine
fixture: `sample_routine.csv` must return `CLEAN`.

## Repo map

```
app.py                 → single entry point: starts backend + frontend together on :8000
run.sh                 → clean-machine runner (venv + pip + python app.py), idempotent
requirements.txt       → all Python dependencies
.env.example           → keys/tunables template (copy to .env, never commit .env)
core/                  → ingest · baseline · rules · retriever · reportgen · service · api
core/web/static/       → the web UI served by app.py (no separate frontend build)
data/                  → generated sample histories (routine + suspicious) + audit.db
tests/                 → pytest suite (one file per module)
docs/ · tasks/         → screenshots, spec and build-plan notes
SPEC.md · SUBMISSION.md → problem spec and submission write-up
```

<!-- New work? The commit history is the plan in motion: one commit per vertical slice. -->

`data/audit.db` and generated data are regenerable from `core/tools/generate_data.py`:

```bash
python -m core.tools.generate_data --out out.csv                 # routine fixture
python -m core.tools.generate_data --suspicious --out out.csv    # suspicious fixture
```

## What it will not do

- It will not call fraud on evidence alone — a `NEEDS REVIEW` verdict is a request
  for an investigator, not a verdict.
- It will not invent transactions: every cited row maps to a real input line.
- It will not make noise on clean histories: each rule is thresholded against the
  customer's own baseline.