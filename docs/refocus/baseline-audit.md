# Baseline Audit

Date: 2026-07-17
Default-branch starting point: `96bbff6` (`docs(G01): UI audit review`)
Local environment: Python 3.14.2, Node v25.8.1, npm 11.11.0

## Verification Commands

These commands were run before the refocus edits that removed non-canonical exploratory surfaces and added the PaperQA2 adapter scaffold.

| Area | Command | Result |
| --- | --- | --- |
| Backend lint | `cd backend && ./.venv/bin/ruff check .` | Pass |
| Backend format | `cd backend && ./.venv/bin/black --check .` | Pass, 22 files unchanged |
| Backend tests | `cd backend && ./.venv/bin/pytest` | Pass, 62 tests, 39 warnings |
| Frontend lint | `cd frontend && npm run lint` | Pass |
| Frontend tests | `cd frontend && npm run test` | Pass, 7 files, 52 tests |
| Frontend build | `cd frontend && npm run build` | Pass with the existing Vite chunk-size warning |

After P0 correctness fixes and worker-flow changes:

| Area | Command | Result |
| --- | --- | --- |
| Backend lint | `cd backend && ./.venv/bin/ruff check .` | Pass |
| Backend format | `cd backend && ./.venv/bin/black --check .` | Pass |
| Backend tests | `cd backend && ./.venv/bin/pytest` | Pass, 67 tests |
| Frontend lint | `cd frontend && npm run lint` | Pass |
| Frontend tests | `cd frontend && npm run test` | Pass |
| Frontend build | `cd frontend && npm run build` | Pass with the existing Vite chunk-size warning |

The final verification for the refocus commit is recorded in the commit message and terminal output after these docs were added.

## Code Map

Canonical implementation path:

- `backend/agent.py`: digest job execution, cache-aware summarization, cost caps, and run-state semantics.
- `backend/main.py`: FastAPI routes, safe error handling, admin-gated cache maintenance, digest/backfill job workers, synthesis, search, and classification.
- `backend/paperqa_adapter.py`: Marginalia paper-to-PaperQA2 document boundary.
- `frontend/src/routes/FeedPage.tsx`, `ArchivePage.tsx`, `SearchPage.tsx`, `SynthesisWorkbenchPage.tsx`, `StatusPage.tsx`: remaining product workflows.
- `frontend/src/lib/api.ts` and `frontend/src/hooks/useDigestApi.ts`: current API client and query/mutation hooks.
- `experiments/e001/`: preregistered PaperQA2 retrieval experiment scaffold.
- `results/e001/`: generated smoke artifacts only; not canonical quality results.

Removed or demoted paths:

- Non-canonical exploratory UI, APIs, schemas, tests, and generated screenshots.
- `.planning/loops` and `.planning/ui-reviews`, which were generated workflow state rather than public scientific evidence.
- Long-range roadmap and loop-engineering docs that did not belong in the technical review path.

## Claim Inventory

Supported by tests or generated artifacts:

- Digest and backfill work now use persisted job rows and idempotent worker endpoints.
- Budget-exhausted runs are not reported as fully successful.
- Unhandled exceptions return a generic client error with a request identifier.
- Search-cache destructive endpoints are disabled unless an admin key is configured.
- The PaperQA2 adapter smoke can be reproduced with `scripts/reproduce_e001.sh experiments/e001/configs/smoke.json`.

Not yet claimed:

- PaperQA2 answer-quality improvement.
- Citation-support improvement.
- Cost-quality frontier for E001.
- Canonical evaluation over official PaperQA2 tasks.
