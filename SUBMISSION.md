# SUBMISSION — PS06 Banking Transaction Risk Investigation Assistant

NexusTiQ24 · Track PS06 · 24-hour solo GenAI build
Repo: `nexustiq24-ps06-banking`

---

## Problem Summary

A bank fraud desk uploads a single customer's transaction history (date, description,
payee, amount, channel) covering several months. The system returns an investigation
report whose **first finding is whether anything needs attention at all** — and says so
plainly when the history is clean.

When review is warranted, the report states:
1. The specific transactions involved and how they connect.
2. The exact risk rule that fired.
3. How the activity differs from this customer's own baseline.
4. What an investigator should look at first.

The system never asserts that fraud has occurred; it flags, explains, and hands
judgment to the investigator. Clean histories return clean.

---

## Prompt Strategy

The system is **deterministic-first, LLM-last**. The Gemini narrative is a grounded
summary of machine-generated evidence — it never decides, only narrates.

A single prompt is assembled in `core/reportgen.py:build_prompt` from four parts:

1. **Hard constraints (the safety guard)** — the model is told:
   - NEVER state or imply fraud has occurred; flag and hand judgment to the investigator.
   - Only cite transaction rows present in the evidence (row N = exact CSV input line).
   - If CLEAN, say so plainly and confidently in 2–3 sentences.
   - If NEEDS REVIEW, lead with what to look at first, then explain each flagged rule and
     how it differs from the baseline.
   - Do not invent numbers not in the evidence.

2. **The deterministic verdict** — `Verifier's verdict (deterministic, do not contradict)`.
   The verdict is computed by rules, not by the LLM, so the model cannot flip a CLEAN case
   into a flag or invent suspicion.

3. **The machine evidence** — the per-customer baseline statistics plus each `RiskFinding`
   (rule id, severity, cited row numbers, evidence string). The LLM is restricted to this.

4. **Similar-history context** — nearest-neighbour transactions from the customer's own
   history (via embeddings + FAISS) so the narrative can say *why* a row is unusual
   relative to genuinely similar prior activity.

The LLM path is fully optional. `core/reportgen.py:generate_report` tries the injected
LLM (test seam), then the Gemini chat API, then a deterministic structured fallback
narrative. A missing/expired key never aborts an investigation.

Model: `gemini-3.6-flash` (flash class, per constraints). Overridable via `GEMINI_MODEL`.

## Embedding Model Choice

- **Embedding model:** `gemini-embedding-001` (only embedding API used, per constraints).
- **Store:** local **FAISS** index (`IndexFlatIP` with L2-normalized inner product), rebuilt
  per investigation from the customer's own history — no hosted vector DB.
- **Purpose:** retrieve the `k` most textually similar *other* transactions for each flagged
  row (`core/retriever.py:Retriever.similar`), excluding the query row itself. This gives the
  narrator concrete "normal lookalikes" to contrast flagged rows against.
- Embedding calls are batched (batch size 100, `core/retriever.py:_batch_embed`) to bound
  per-request size on large histories. If no key is present, the retriever is skipped and the
  narrative runs on rules alone (graceful degradation).

## Eval Results

All deterministic. `python -m pytest -q` → **56 passed**.

| Case | Expected | Actual |
|---|---|---|
| `data/sample_routine.csv` (routine history) | CLEAN — no false positives | CLEAN ✔ |
| `data/sample_suspicious.csv` (crafted anomalies) | NEEDS REVIEW, every finding row-cited | NEEDS REVIEW ✔ |
| Missing/expired `GEMINI_API_KEY` | Deterministic narrative, investigation succeeds | fallback narrative ✔ |
| Extra columns / multiple date formats | Tolerant parse, row traceability preserved | parsed ✔ |
| Oversized upload / row cap | Bounded (20 MB, 10,000 rows) | rejected gracefully ✔ |

Hard-rule coverage is enforced in tests: every cited row is traceable to input
(`tests/test_ingest.py`, `test_rules.py`), the pipeline never emits "fraud"
(`tests/test_reportgen.py`), and routine fixtures stay clean (`test_service.py`,
`test_rules.py`).

## Known Limitations

- **Synthetic data only.** The sample CSVs are generated, not real customer data. No
  real-world validation of thresholds yet.
- **Within-customer baseline.** Rules compare a row to the *same customer's* history, so a
  customer with consistently unusual behavior may have a "loose" baseline. This is by design
  (avoid false positives) but means truly novel abuse can appear normal.
- **Embedding similarity is textual, not semantic-investigation-grade.** It finds similar
  descriptions/payees, not fraud *networks*. It only enriches the narrative; it never gates
  the verdict.
- **Deterministic threshold tuning is heuristic.** Rule thresholds were tuned on the
  synthetic fixtures; a larger labeled set would firm them up.
- **No multi-customer / network view.** Single-account input only.
- **Gemini endpoints.** Both the language and embedding paths call the public Gemini API and
  need a network + key; the deterministic fallback covers offline.

---

## Submission checklist

- [x] Code in repo, runs via `bash run.sh` on `http://0.0.0.0:8000`
- [x] Sample CSVs (`data/sample_routine.csv`, `data/sample_suspicious.csv`)
- [x] UI screenshots (`docs/screenshots/`)
- [x] README (run, API, input schema, architecture, repo map)
- [x] Final git tag `hackathon-track-ps06-v1.0`
- [x] `.env` (real key) NOT in repo — only `.env.example` placeholder
