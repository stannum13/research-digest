# Marginalia

Marginalia is a budget-aware research briefing and evidence workspace built on grounded scientific retrieval.

## Current Status

| Surface | Status | Evidence |
| --- | --- | --- |
| Briefing product | Working local FastAPI + React app with seed data, arXiv ingestion, saved papers, feedback, search, classification, cost accounting, and selected-paper synthesis | Backend/frontend tests and builds |
| P0 correctness | Safe exception responses, budget-exhausted run states, persisted digest/backfill jobs, pinned CI actions, and admin-gated cache deletes | `docs/refocus/baseline-audit.md` |
| PaperQA2 integration | Upstream pinned; local Marginalia-to-PaperQA2 document adapter covered by smoke output | `UPSTREAM.md`, `backend/paperqa_adapter.py`, `results/e001/summary.json` |
| E001 canonical result | Not run yet | `experiments/e001/configs/canonical.json` is intentionally disabled |

## Question

Can a small reranker plus adaptive evidence stopping reduce scientific retrieval and synthesis cost while preserving PaperQA2 answer quality and citation support?

## Method

Marginalia keeps product-specific ingestion, paper state, feedback, cost accounting, and UI code in this repository. PaperQA2 is the upstream substrate for the scientific retrieval experiment.

The current implementation delta is small:

- `backend/paperqa_adapter.py` converts stored paper records into citation-preserving document specs for PaperQA2 ingestion.
- `scripts/reproduce_e001.sh` generates deterministic E001 smoke artifacts from the checked-in config.
- The existing app keeps digest and synthesis workflows budget-aware and auditable while non-canonical exploratory features are out of the public main path.

## Reproduce

Smoke artifact:

```bash
scripts/reproduce_e001.sh experiments/e001/configs/smoke.json
```

Canonical E001:

```bash
scripts/reproduce_e001.sh experiments/e001/configs/canonical.json
```

The canonical command is expected to stop until `experiments/e001/configs/canonical.json` is enabled with a selected PaperQA2 evaluation task, provider credentials, budget, and predeclared tolerances. Do not treat smoke output as a quality result.

Local app verification:

```bash
cd backend
./.venv/bin/ruff check .
./.venv/bin/black --check .
./.venv/bin/pytest

cd ../frontend
npm run lint
npm run test
npm run build
```

## Repository Map

| Path | Why inspect it |
| --- | --- |
| `UPSTREAM.md` | PaperQA2 repository/package pin and integration boundary |
| `experiments/e001/experiment.md` | E001 hypothesis, baselines, controls, metrics, and promotion rule |
| `experiments/e001/configs/` | Smoke and canonical configurations |
| `results/e001/` | Generated smoke manifest, summary, CSV, and status figure |
| `backend/paperqa_adapter.py` | Current PaperQA2-facing adapter |
| `backend/agent.py` | Digest run execution, caching, and cost-cap semantics |
| `backend/main.py` | API routes, safe errors, admin gate, and worker endpoints |
| `frontend/src/routes/` | Product UI for feed, archive, search, synthesis, status, and saved papers |
| `docs/refocus/baseline-audit.md` | Verification history and claim inventory |
| `docs/limitations.md` | Evidence boundaries and external-validity limits |

## Evidence Boundary

- Measured: local test/build pass state and E001 adapter-smoke artifact generation.
- Implemented: persisted digest/backfill jobs, safe API error handling, budget-exhausted status semantics, admin-gated destructive cache operations, and PaperQA2 document shaping.
- Inferred: the adapter is suitable for PaperQA2 ingestion based on its citation-preserving document shape.
- Not tested yet: PaperQA2 answer quality, citation support, cost-quality frontier, latency, source diversity, or subdomain failure rates.

## Limitations

The seed dataset is for product smoke testing, not scientific evaluation. The E001 smoke run checks adapter shape only. Any PaperQA2 result must be generated from a declared evaluation task with raw per-question traces, deterministic summaries, and predeclared quality/citation tolerances.

More detail is in `docs/limitations.md`.

## License and Attribution

No license file is currently checked in, so treat this repository as unlicensed unless a license is added later.

PaperQA2 is maintained upstream at `https://github.com/Future-House/paper-qa`; the current pin and package version are recorded in `UPSTREAM.md`.
