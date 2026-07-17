# Architecture

Marginalia is a small full-stack research workspace with three boundaries:

1. **Briefing pipeline**: fetch arXiv candidates, normalize metadata, rank papers, summarize a bounded shortlist, and record digest/backfill job state.
2. **Evidence workspace**: store saved papers, feedback, deterministic labels, selected-paper synthesis runs, retrieval-search cache entries, and provider cost records.
3. **PaperQA2 adapter**: convert Marginalia paper records into citation-preserving document specs for the E001 scientific retrieval experiment.

## System Diagram

```txt
arXiv API
  |
  v
backend/arxiv_client.py -> normalization/base-ID dedupe
  |
  v
SQLite papers + paper_breakdowns
  |
  v
backend/ranking.py -> bounded shortlist
  |
  v
backend/summarizer.py -> optional provider summary + llm_calls
  |
  v
FastAPI routes in backend/main.py
  |
  v
React + TanStack Query frontend

papers + breakdowns
  |
  v
backend/paperqa_adapter.py
  |
  v
PaperQA2 document specs for E001
```

## Backend Map

| Module | Responsibility |
| --- | --- |
| `settings.py` | Environment-driven database, arXiv, scheduler, provider, budget, and admin settings |
| `database.py` | SQLAlchemy setup, initialization, and lightweight SQLite upgrades |
| `models.py` | Papers, breakdowns, runs, backfill jobs, feedback, labels, synthesis, caches, and LLM usage |
| `schemas.py` | Pydantic request/response contracts |
| `seed.py` | Seed papers for no-key local use |
| `arxiv_client.py` | arXiv fetch and normalization |
| `ranking.py` | Deterministic pre-provider scoring and diversity |
| `fulltext.py` | Optional full-text extraction for shortlisted papers |
| `summarizer.py` | Provider abstraction, summary validation/repair, fallback summaries, and cost estimates |
| `agent.py` | Digest execution, cache reuse, persisted run state, and budget-cap semantics |
| `classification.py` | Deterministic paper labels used by search and status coverage |
| `synthesis.py` | Selected-paper synthesis with source discipline |
| `evidence_audit.py` | Source-support checks for synthesis outputs |
| `paperqa_adapter.py` | Marginalia-to-PaperQA2 document conversion |
| `main.py` | FastAPI app, routes, safe errors, admin gate, and worker endpoints |

## Data Model

Current primary tables:

```txt
papers
paper_breakdowns
paper_summary_cache
retrieval_search_cache
paper_classifications
synthesis_runs
synthesis_run_papers
digest_runs
backfill_jobs
llm_calls
feedback
preferences
```

Important invariants:

- `papers.arxiv_id` stores the base arXiv ID and is unique.
- `paper_breakdowns` are optional because fetched papers can exist before summarization.
- `digest_runs.status` distinguishes `pending`, `running`, `success`, `failed`, `partial`, and `budget_exhausted`.
- `backfill_jobs` advance one unfinished date at a time through an idempotent worker endpoint.
- `llm_calls` records task, provider, model, tokens, and estimated cost for accountable provider usage.
- `paper_summary_cache` prevents repeated summary calls for the same paper/provider/model/prompt version.
- `retrieval_search_cache` stores normalized search responses and hit counts.
- `paper_classifications` stores deterministic labels that support search and coverage status.
- `synthesis_runs` store selected-source research notes with source paper associations.

## API Surface

Core routes:

```txt
GET    /health
GET    /papers
GET    /papers/saved
GET    /papers/{arxiv_id}
POST   /papers/{arxiv_id}/save
POST   /papers/{arxiv_id}/feedback
GET    /papers/{arxiv_id}/classifications
POST   /papers/{arxiv_id}/classify
GET    /search
GET    /search/cache/status
DELETE /search/cache
DELETE /search/cache/{cache_id}
GET    /digest/latest
POST   /digest/run
POST   /digest/runs/{run_id}/run
GET    /digest/runs/{run_id}
GET    /digest/status
POST   /backfill/jobs
GET    /backfill/jobs
GET    /backfill/jobs/{job_id}
POST   /backfill/jobs/{job_id}/run
GET    /classifications/status
POST   /classifications/run
POST   /synthesis/runs
GET    /synthesis/runs
GET    /synthesis/runs/{run_id}
GET    /stats
```

Route notes:

- Unhandled exceptions are logged server-side and returned to clients as generic errors with request IDs.
- Cache deletion is unavailable unless `ADMIN_API_KEY` is configured and the caller sends `x-admin-key`.
- `POST /digest/run` creates a persisted job; `POST /digest/runs/{run_id}/run` executes it.
- `POST /backfill/jobs/{job_id}/run` advances a runnable job by one date and can be called repeatedly.

## Frontend Map

The frontend is a Vite React app using TanStack Query, React Router, Tailwind, and Framer Motion.

| Path | Responsibility |
| --- | --- |
| `src/App.tsx` | Route registration |
| `src/components/AppShell.tsx` | Layout and navigation shell |
| `src/components/Sidebar.tsx` | Desktop and mobile nav |
| `src/components/PaperCard.tsx` | Paper object, expansion, classifications, feedback, and selection |
| `src/routes/FeedPage.tsx` | Main feed query/filter/load-more behavior |
| `src/routes/ArchivePage.tsx` | Historical date/category browsing |
| `src/routes/SearchPage.tsx` | Keyword and label retrieval |
| `src/routes/SynthesisWorkbenchPage.tsx` | Selected-paper synthesis |
| `src/routes/StatusPage.tsx` | Run status, accounting, classifications, backfills, and search-cache maintenance |
| `src/lib/api.ts` | Fetch wrapper and API methods |
| `src/hooks/useDigestApi.ts` | Query and mutation hooks |
| `src/types/api.ts` | TypeScript API contracts |

## Verification

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
