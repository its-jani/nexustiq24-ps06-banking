# Tasks: PS06 Banking Transaction Risk Investigation Assistant

All tasks sized S/M (<~5 files). Build in dependency order.
Commit after each completed slice (repo always working).

- [ ] **T1 Scaffold**
  - Acceptance: repo has SPEC.md, tasks/plan.md, README.md, run.sh, requirements.txt, .env.example; git first commit
  - Verify: `git log` shows commit 1; `run.sh --help`-equivalent parses
  - Files: SPEC.md, tasks/plan.md, tasks/todo.md, README.md, run.sh, requirements.txt, .gitignore, .env.example
- [ ] **T2 ingest**
  - Acceptance: parse valid CSV; reject missing/blank/invalid rows with row numbers; `row` field preserves 1-based input index; extra columns tolerated; date formats ISO + MM/DD/YYYY
  - Verify: `pytest tests/test_ingest.py -q`
  - Files: app/models.py, app/ingest.py, tests/test_ingest.py
- [ ] **T3 baseline**
  - Acceptance: per-direction amount stats (mean/std/median/IQR), channel distribution, payee set + unseen detection, timing stats; deterministic values on fixture
  - Verify: `pytest tests/test_baseline.py -q`
  - Files: app/baseline.py, tests/test_baseline.py
- [ ] **T4 rules**
  - Acceptance: rules flat_outlier, rapid_sequence, round_amount, channel_anomaly, new_payee_large, high_velocity_freq; each emits RiskFinding with rule_id/severity/rows/evidence; routine fixture yields zero findings
  - Verify: `pytest tests/test_rules.py -q`
  - Files: app/rules.py, tests/test_rules.py
- [ ] **T5 retriever**
  - Acceptance: embeds transactions (gemini-embedding-001), builds local FAISS index, returns top-k similar historic rows; no-key → graceful skip
  - Verify: `pytest tests/test_retriever.py -q` (embedding stub)
  - Files: app/retriever.py, tests/test_retriever.py
- [ ] **T6 reportgen**
  - Acceptance: builds Gemini prompt from evidence; injectable llm fn (test stub); no-key fallback narrative; never asserts fraud; cites only provided rows
  - Verify: `pytest tests/test_reportgen.py -q`
  - Files: app/reportgen.py, tests/test_reportgen.py
- [ ] **T7 service**
  - Acceptance: orchestrates ingest→baseline→rules→retriever→reportgen; returns InvestigationReport(verdict, findings, cited_transactions, narrative, summary); CLEAN on routine file, NEEDS REVIEW on crafted file
  - Verify: `pytest tests/test_service.py -q`
  - Files: app/service.py, tests/test_service.py
- [ ] **T8 api**
  - Acceptance: POST /investigate (multipart), GET /investigate/{id}, GET /health; each case stored in SQLite; single-page UI in browser with upload + rendered report
  - Verify: `pytest tests/test_api.py -q` + manual browser check
  - Files: app/config.py, app/db.py, app/main.py, app/web/static/index.html, tests/test_api.py
- [ ] **T9 data tools + full suite**
  - Acceptance: generate_data.py makes routine + suspicious CSVs; cli.py runs a file end-to-end; full `pytest -q` green
  - Verify: `python -m pytest -q`; run cli on both sample files
  - Files: app/tools/generate_data.py, app/tools/cli.py, data/sample_routine.csv, data/sample_suspicious.csv, tests/* updates
- [ ] **T10 REVIEW/SHIP**
  - Acceptance: code review pass (doubt-driven), security check (no secrets, input validation, bounded payloads), README final, `bash run.sh` boots on clean env, audit trail verified
  - Verify: `pytest -q`; `pip check`; README walkthrough executed
  - Files: README.md, any review fixes

## Lifecycle mapping
DEFINE→T1 · PLAN→T1 · BUILD→T2..T9 · VERIFY→T9,T10 · REVIEW→T10 · SHIP→T10