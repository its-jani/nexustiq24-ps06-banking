# Plan: PS06 Banking Transaction Risk Investigation Assistant

## Architecture

Deterministic evidence layer + LLM presentation layer. The LLM **never decides**:
rules and baseline statistics produce machine-readable, row-traceable findings; the
Gemini narrative is a grounded summary of that evidence. This is what keeps hard
rules 1-5 satisfiable even when the model or key is absent.

```
CSV ──▶ ingest ──▶ baseline ──▶ rules ──┐
        │                ▲              │
        └──▶ retriever ──┘              ▼
        (embeddings+FAISS for similar-history context)   reportgen (Gemini)
                                              ▲              │
                                              └── evidence ──┤
                                                             ▼
                                              InvestigationReport (JSON + narrative)
                                                             │
                                              sqlite audit (case id) + web UI / API
```

## Vertical Slices (build order = dependency order)

1. **ingest** — CSV schema, dataclasses, validation, row traceability. No deps.
2. **baseline** — amount/channel/payee/timing statistics; depends on ingest.
3. **rules** — deterministic rule engine; depends on ingest + baseline.
4. **retriever** — embedding calls + FAISS local index; depends on ingest (adds context for reportgen, does not gate verdict).
5. **reportgen** — Gemini synthesis with injected stub seam + no-key fallback; depends on ingest/baseline/rules/retriever outputs.
6. **service** — orchestrator assembling InvestigationReport; depends on 1-5.
7. **api** — FastAPI routes, SQLite audit, single-page UI; depends on service.

Parallelizable: 1-3 are a strict chain; retriever (4) can start in parallel with 3.
Each slice ends with tests green before the next starts (incremental-implementation).

## Commit Plan

One commit per completed vertical slice plus a doc/scaffold gate and a final
review/ship gate — ~10 commits total, each leaving the repo in a working state:

1. scaffold (spec / plan / tasks / README / run.sh / requirements)
2. ingest
3. baseline
4. rules
5. retriever
6. reportgen
7. service
8. api (server + audit + UI)
9. data tools + full test suite + clean-run verification
10. review/hardening + final README + run verification

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| API key absent on judge machine | Verdict/findings are deterministic; narrative falls back to structured text |
| Model hallucinates a transaction row | Narrative is generated from evidence JSON; machine findings remain the source of truth; UI shows both |
| False positives on routine data | Rules are thresholded on within-customer baselines, tuned on synthetic routine fixtures, and covered by CLEAN-case tests |
| Nonstandard CSV | Tolerant parser: extra columns ignored, common date formats, clear validation errors for missing required columns |
| Environment differences (judge machine) | `run.sh` idempotent install; pinned requirements; no build step; stdlib-only persistence |

## Verification Checkpoints

- After ship: `pytest -q` green; `run.sh` boots; routine CSV returns CLEAN; crafted CSV returns NEEDS REVIEW with cited rows.