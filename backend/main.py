import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from agent import run_digest
from arxiv_client import normalize_arxiv_id
from classification import LABEL_TYPES, list_paper_classifications
from classification import classify_paper as classify_paper_records
from database import get_db, init_db
from models import (
    BackfillJob,
    DigestRun,
    Feedback,
    LLMCall,
    Paper,
    PaperBreakdown,
    PaperClassification,
    RetrievalSearchCache,
    SynthesisRun,
    SynthesisRunPaper,
)
from scheduler import shutdown_scheduler, start_scheduler
from schemas import (
    ApiError,
    BackfillJobIn,
    BackfillJobOut,
    BackfillJobsResponse,
    BackfillStatusName,
    ClassificationRunOut,
    ClassificationStatusOut,
    DigestLatestResponse,
    DigestRunDetailOut,
    DigestRunIn,
    DigestRunOut,
    DigestStatusOut,
    FeedbackIn,
    FeedbackOut,
    LLMCallOut,
    PaperBreakdownOut,
    PaperClassificationOut,
    PaperClassificationsResponse,
    PapersResponse,
    PaperWithBreakdown,
    SearchCacheDeleteResponse,
    SearchCacheEntryOut,
    SearchCacheStatusOut,
    SearchResponse,
    SearchResultOut,
    StatsOut,
    SynthesisRunDetailOut,
    SynthesisRunIn,
    SynthesisRunsResponse,
    SynthesisRunSummaryOut,
)
from seed import seed_if_empty
from settings import get_settings
from synthesis import (
    MAX_SYNTHESIS_PAPERS,
    SYNTHESIS_MODEL_NAME,
    SYNTHESIS_MODEL_PROVIDER,
    SYNTHESIS_PROMPT_VERSION,
    SYNTHESIS_TASK,
    build_synthesis,
)

settings = get_settings()
logger = logging.getLogger("digest.api")
RETRIEVAL_SEARCH_CACHE_VERSION = "retrieval-search-v1"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = next(get_db())
    try:
        if settings.seed_on_empty:
            seed_if_empty(db)
    finally:
        db.close()
    start_scheduler(settings)
    yield
    shutdown_scheduler()


app = FastAPI(title="Marginalia API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else None
    error = detail or status.HTTP_STATUS_CODES.get(exc.status_code, "API error")
    return JSONResponse(status_code=exc.status_code, content=ApiError(error=error, detail=detail).model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    logger.error(
        "Unhandled API error",
        extra={"request_id": request_id, "path": request.url.path, "method": request.method},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=ApiError(error="Internal server error", detail=f"Request ID: {request_id}").model_dump(),
    )


def require_admin_access(request: Request) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=404, detail="Administrative endpoint disabled")
    if request.headers.get("x-admin-key") != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid administrative key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/papers/saved", response_model=PapersResponse)
def get_saved_papers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PapersResponse:
    return _query_papers(db=db, saved=True, page=page, page_size=page_size)


@app.get("/papers", response_model=PapersResponse)
def get_papers(
    date: str | None = None,
    category: str | None = None,
    saved: bool | None = None,
    difficulty: str | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PapersResponse:
    return _query_papers(
        db=db,
        date=date,
        category=category,
        saved=saved,
        difficulty=difficulty,
        q=q,
        page=page,
        page_size=page_size,
    )


@app.get("/search", response_model=SearchResponse)
def search_papers(
    q: str | None = None,
    label_type: str | None = None,
    label: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    normalized_q, normalized_label_type, normalized_label = _search_cache_inputs(
        q=q,
        label_type=label_type,
        label=label,
    )
    cached = _get_search_cache_entry(
        db=db,
        normalized_q=normalized_q,
        normalized_label_type=normalized_label_type,
        normalized_label=normalized_label,
        limit=limit,
    )
    if cached is not None:
        cached.hit_count += 1
        cached.last_hit_at = datetime.now(UTC)
        db.commit()
        return SearchResponse.model_validate_json(cached.response_json)

    results = _search_papers(
        db=db,
        q=normalized_q,
        label_type=normalized_label_type,
        label=normalized_label,
        limit=limit,
    )
    response = SearchResponse(items=results, total=len(results), query=normalized_q)
    _store_search_cache_entry(
        db=db,
        normalized_q=normalized_q,
        normalized_label_type=normalized_label_type,
        normalized_label=normalized_label,
        limit=limit,
        response=response,
    )
    return response


@app.get("/search/cache/status", response_model=SearchCacheStatusOut)
def get_search_cache_status(db: Session = Depends(get_db)) -> SearchCacheStatusOut:
    return _search_cache_status(db)


@app.delete("/search/cache", response_model=SearchCacheDeleteResponse)
def clear_search_cache(
    _admin: None = Depends(require_admin_access),
    db: Session = Depends(get_db),
) -> SearchCacheDeleteResponse:
    return _delete_search_cache_entries(db)


@app.delete("/search/cache/{cache_id}", response_model=SearchCacheDeleteResponse)
def delete_search_cache_entry(
    cache_id: int,
    _admin: None = Depends(require_admin_access),
    db: Session = Depends(get_db),
) -> SearchCacheDeleteResponse:
    return _delete_search_cache_entries(db, cache_id=cache_id)


@app.get("/papers/{arxiv_id}", response_model=PaperWithBreakdown)
def get_paper(arxiv_id: str, db: Session = Depends(get_db)) -> PaperWithBreakdown:
    paper = _get_paper_or_404(db, arxiv_id)
    return _paper_to_schema(paper)


@app.post("/papers/{arxiv_id}/classify", response_model=PaperClassificationsResponse)
def classify_paper(arxiv_id: str, db: Session = Depends(get_db)) -> PaperClassificationsResponse:
    paper = _get_paper_or_404(db, arxiv_id)
    classifications = classify_paper_records(db, paper)
    return _paper_classifications_to_schema(paper, classifications)


@app.get("/papers/{arxiv_id}/classifications", response_model=PaperClassificationsResponse)
def get_paper_classifications(arxiv_id: str, db: Session = Depends(get_db)) -> PaperClassificationsResponse:
    paper = _get_paper_or_404(db, arxiv_id)
    classifications = list_paper_classifications(db, paper)
    return _paper_classifications_to_schema(paper, classifications)


@app.post("/classifications/run", response_model=ClassificationRunOut)
def run_classifications(
    limit: int | None = Query(default=None, ge=1, le=1000),
    only_missing: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ClassificationRunOut:
    papers = _classification_run_papers(db, limit=limit, only_missing=only_missing)
    for paper in papers:
        classify_paper_records(db, paper)

    return ClassificationRunOut(
        only_missing=only_missing,
        limit=limit,
        papers_processed=len(papers),
        paper_ids=[paper.id for paper in papers],
        arxiv_ids=[paper.arxiv_id for paper in papers],
        status=_classification_status(db),
    )


@app.get("/classifications/status", response_model=ClassificationStatusOut)
def get_classification_status(db: Session = Depends(get_db)) -> ClassificationStatusOut:
    return _classification_status(db)


@app.post("/papers/{arxiv_id}/save", response_model=PaperWithBreakdown)
def toggle_save(arxiv_id: str, db: Session = Depends(get_db)) -> PaperWithBreakdown:
    paper = _get_paper_or_404(db, arxiv_id)
    paper.is_saved = not paper.is_saved
    db.commit()
    db.refresh(paper)
    return _paper_to_schema(paper)


@app.post("/papers/{arxiv_id}/feedback", response_model=FeedbackOut)
def create_feedback(arxiv_id: str, payload: FeedbackIn, db: Session = Depends(get_db)) -> FeedbackOut:
    paper = _get_paper_or_404(db, arxiv_id)
    feedback = Feedback(paper_id=paper.id, signal=payload.signal, note=payload.note)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return FeedbackOut(
        id=feedback.id,
        paper_id=feedback.paper_id,
        signal=feedback.signal,
        note=feedback.note,
        created_at=feedback.created_at,
    )


@app.post("/synthesis/runs", response_model=SynthesisRunDetailOut, status_code=status.HTTP_201_CREATED)
def create_synthesis_run(payload: SynthesisRunIn, db: Session = Depends(get_db)) -> SynthesisRunDetailOut:
    papers = _resolve_synthesis_papers(db, payload)
    output = build_synthesis(papers=papers, mode=payload.mode, instructions=payload.instructions, settings=settings)
    run = SynthesisRun(
        mode=payload.mode,
        instructions=payload.instructions,
        argument_map_json=_json_dump(output["argument_map"]),
        contradictions_json=_json_dump(output["contradictions"]),
        evidence_matrix_json=_json_dump(output["evidence_matrix"]),
        open_questions_json=_json_dump(output["open_questions"]),
        extension_ideas_json=_json_dump(output["extension_ideas"]),
        replication_or_ablation_plan_json=_json_dump(output["replication_or_ablation_plan"]),
        caveats_json=_json_dump(output["caveats"]),
        source_paper_ids_json=_json_dump(output["source_paper_ids"]),
        prompt_version=str(output["prompt_version"]),
        model_provider=str(output["model_provider"]),
        model_name=str(output["model_name"]),
    )
    db.add(run)
    db.flush()
    for position, paper in enumerate(papers):
        db.add(SynthesisRunPaper(run_id=run.id, paper_id=paper.id, position=position))
    _record_synthesis_usage(db=db, run=run, output=output)
    db.commit()
    db.refresh(run)
    return _synthesis_run_detail_to_schema(db, run)


@app.get("/synthesis/runs", response_model=SynthesisRunsResponse)
def list_synthesis_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SynthesisRunsResponse:
    query = db.query(SynthesisRun)
    total = query.count()
    runs = (
        query.order_by(SynthesisRun.created_at.desc(), SynthesisRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SynthesisRunsResponse(
        items=[_synthesis_run_to_summary(run) for run in runs],
        page=page,
        page_size=page_size,
        total=total,
    )


@app.get("/synthesis/runs/{run_id}", response_model=SynthesisRunDetailOut)
def get_synthesis_run(run_id: int, db: Session = Depends(get_db)) -> SynthesisRunDetailOut:
    run = db.get(SynthesisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Synthesis run not found")
    return _synthesis_run_detail_to_schema(db, run)


@app.get("/digest/latest", response_model=DigestLatestResponse)
def get_latest_digest(db: Session = Depends(get_db)) -> DigestLatestResponse:
    run = (
        db.query(DigestRun)
        .filter(DigestRun.status.in_(("success", "partial", "budget_exhausted")))
        .order_by(DigestRun.started_at.desc())
        .first()
    )
    papers = (
        db.query(Paper)
        .options(joinedload(Paper.breakdown))
        .filter(Paper.is_summarized.is_(True))
        .order_by(Paper.score.desc().nullslast(), Paper.published_at.desc())
        .limit(settings.top_n)
        .all()
    )
    return DigestLatestResponse(
        run=_run_to_schema(run) if run else None,
        papers=[_paper_to_schema(paper) for paper in papers],
    )


@app.post("/digest/run", response_model=DigestRunOut)
def trigger_digest(
    payload: DigestRunIn | None = Body(default=None),
    db: Session = Depends(get_db),
) -> DigestRunOut:
    payload = payload or DigestRunIn()
    run = _create_digest_job(db, payload)
    out = _run_to_schema(run)
    out.message = "Digest job created. Run it with POST /digest/runs/{id}/run."
    return out


@app.post("/digest/runs/{run_id}/run", response_model=DigestRunOut)
def run_digest_job(run_id: int, db: Session = Depends(get_db)) -> DigestRunOut:
    existing = db.get(DigestRun, run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Digest run not found")
    if existing.status == "running":
        out = _run_to_schema(existing)
        out.message = "Digest job is already running."
        return out
    if existing.status in {"success", "budget_exhausted"}:
        out = _run_to_schema(existing)
        out.message = "Digest job already reached a terminal state."
        return out
    if existing.status not in {"pending", "failed"}:
        raise HTTPException(status_code=400, detail=f"Digest job cannot run from {existing.status} state")

    run = run_digest(
        db,
        settings,
        target_date=existing.target_date,
        category_scope=_run_category_scope(existing),
        backfill_job_id=existing.backfill_job_id,
        run_id=existing.id,
    )
    out = _run_to_schema(run)
    if run.status == "success":
        out.message = "Digest job completed."
    elif run.status == "budget_exhausted":
        out.message = "Digest job stopped because its budget was exhausted."
    else:
        out.message = "Digest job failed."
    return out


@app.get("/digest/runs/{run_id}", response_model=DigestRunDetailOut)
def get_digest_run(run_id: int, db: Session = Depends(get_db)) -> DigestRunDetailOut:
    run = db.get(DigestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Digest run not found")
    return _run_detail_to_schema(db, run)


@app.get("/digest/status", response_model=DigestStatusOut)
def get_digest_status(db: Session = Depends(get_db)) -> DigestStatusOut:
    return _digest_status(db)


@app.post("/backfill/jobs", response_model=BackfillJobOut, status_code=status.HTTP_201_CREATED)
def create_backfill_job(payload: BackfillJobIn, db: Session = Depends(get_db)) -> BackfillJobOut:
    category_scope = _normalize_category_scope(payload.category_scope)
    if payload.category_scope is not None and not category_scope:
        raise HTTPException(status_code=400, detail="category_scope must include at least one non-empty category")

    categories = category_scope or settings.category_list
    job = BackfillJob(
        start_date=payload.start_date,
        end_date=payload.end_date,
        category_scope_json=json.dumps(categories),
        status="pending",
        budget_usd=payload.budget_usd if payload.budget_usd is not None else max(settings.llm_run_budget_usd, 0.0),
        total_days=(payload.end_date - payload.start_date).days + 1,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _backfill_job_to_schema(
        job,
        message="Backfill job created. Digest runs were not started automatically.",
    )


@app.get("/backfill/jobs", response_model=BackfillJobsResponse)
def list_backfill_jobs(
    job_status: BackfillStatusName | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> BackfillJobsResponse:
    query = db.query(BackfillJob)
    if job_status:
        query = query.filter(BackfillJob.status == job_status)

    total = query.count()
    jobs = (
        query.order_by(BackfillJob.created_at.desc(), BackfillJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return BackfillJobsResponse(
        items=[_backfill_job_to_schema(job) for job in jobs],
        page=page,
        page_size=page_size,
        total=total,
    )


@app.get("/backfill/jobs/{job_id}", response_model=BackfillJobOut)
def get_backfill_job(job_id: int, db: Session = Depends(get_db)) -> BackfillJobOut:
    job = db.get(BackfillJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Backfill job not found")
    return _backfill_job_to_schema(job)


@app.post("/backfill/jobs/{job_id}/run", response_model=BackfillJobOut)
def run_backfill_job(job_id: int, db: Session = Depends(get_db)) -> BackfillJobOut:
    job = db.get(BackfillJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Backfill job not found")
    if job.status in {"success", "canceled"}:
        raise HTTPException(status_code=400, detail=f"Backfill job cannot run from {job.status} state")

    categories = [str(category) for category in _json_list(job.category_scope_json)] or settings.category_list
    if job.status != "running":
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        job.error_message = None
    _sync_backfill_job_metrics(db, job)
    db.commit()
    db.refresh(job)

    try:
        for target_date in _date_range(job.start_date, job.end_date):
            if _backfill_date_succeeded(db, job.id, target_date):
                continue

            _sync_backfill_job_metrics(db, job)
            if _backfill_budget_exhausted(job):
                _finish_backfill_job(
                    db,
                    job,
                    status_name="budget_exhausted",
                    error_message=f"Backfill budget exhausted before processing {target_date.isoformat()}.",
                )
                return _backfill_job_to_schema(job, message="Backfill job stopped because its budget was exhausted.")

            run = run_digest(
                db,
                settings,
                target_date=target_date,
                category_scope=categories,
                backfill_job_id=job.id,
            )
            if run.backfill_job_id != job.id:
                run.backfill_job_id = job.id
                db.commit()
                db.refresh(run)

            _sync_backfill_job_metrics(db, job)
            if run.status == "budget_exhausted":
                run_error = run.error_message or "Digest run budget was exhausted"
                _finish_backfill_job(
                    db,
                    job,
                    status_name="budget_exhausted",
                    error_message=f"Digest budget exhausted for {target_date.isoformat()}: {run_error}",
                )
                return _backfill_job_to_schema(job, message="Backfill job stopped because its budget was exhausted.")
            if run.status != "success":
                run_error = run.error_message or "Digest run failed"
                _finish_backfill_job(
                    db,
                    job,
                    status_name="failed",
                    error_message=f"Digest failed for {target_date.isoformat()}: {run_error}",
                )
                return _backfill_job_to_schema(job, message="Backfill job failed.")

            next_target_date = _next_backfill_date(db, job)
            if next_target_date is None:
                _sync_backfill_job_metrics(db, job)
                _finish_backfill_job(db, job, status_name="success", error_message=None)
                return _backfill_job_to_schema(job, message="Backfill job completed.")
            if _backfill_budget_exhausted(job):
                _finish_backfill_job(
                    db,
                    job,
                    status_name="budget_exhausted",
                    error_message=f"Backfill budget exhausted before processing {next_target_date.isoformat()}.",
                )
                return _backfill_job_to_schema(job, message="Backfill job stopped because its budget was exhausted.")

            job.status = "running"
            db.commit()
            db.refresh(job)
            return _backfill_job_to_schema(job, message="Backfill job advanced one day.")

        _sync_backfill_job_metrics(db, job)
        _finish_backfill_job(db, job, status_name="success", error_message=None)
        return _backfill_job_to_schema(job, message="Backfill job completed.")
    except Exception as exc:
        db.rollback()
        job = db.get(BackfillJob, job_id)
        if job is None:
            raise
        _sync_backfill_job_metrics(db, job)
        _finish_backfill_job(db, job, status_name="failed", error_message=str(exc))
        return _backfill_job_to_schema(job, message="Backfill job failed.")


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    category_counts = dict(
        db.query(Paper.primary_category, func.count(Paper.id)).group_by(Paper.primary_category).all()
    )
    return StatsOut(
        papers_total=db.query(Paper).count(),
        papers_summarized=db.query(Paper).filter(Paper.is_summarized.is_(True)).count(),
        papers_saved=db.query(Paper).filter(Paper.is_saved.is_(True)).count(),
        feedback_total=db.query(Feedback).count(),
        digest_runs_total=db.query(DigestRun).count(),
        llm_calls_total=db.query(LLMCall).count(),
        llm_tokens_total=db.query(func.coalesce(func.sum(LLMCall.total_tokens), 0)).scalar(),
        estimated_llm_cost_usd=round(db.query(func.coalesce(func.sum(LLMCall.estimated_cost_usd), 0.0)).scalar(), 6),
        categories=category_counts,
    )


def _query_papers(
    db: Session,
    page: int,
    page_size: int,
    date: str | None = None,
    category: str | None = None,
    saved: bool | None = None,
    difficulty: str | None = None,
    q: str | None = None,
) -> PapersResponse:
    query = db.query(Paper).options(joinedload(Paper.breakdown))

    if date:
        try:
            target_date = datetime.fromisoformat(date).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
        start = datetime.combine(target_date, time.min, tzinfo=UTC)
        end = datetime.combine(target_date, time.max, tzinfo=UTC)
        query = query.filter(Paper.published_at >= start, Paper.published_at <= end)

    if category:
        categories = [item.strip() for item in category.split(",") if item.strip()]
        query = query.filter(
            or_(Paper.primary_category.in_(categories), *[Paper.categories_json.contains(item) for item in categories])
        )

    if saved is not None:
        query = query.filter(Paper.is_saved.is_(saved))

    if difficulty:
        query = query.join(PaperBreakdown).filter(PaperBreakdown.difficulty == difficulty)

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Paper.title.ilike(term), Paper.abstract.ilike(term), Paper.authors_json.ilike(term)))

    total = query.count()
    papers = (
        query.order_by(Paper.score.desc().nullslast(), Paper.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PapersResponse(
        items=[_paper_to_schema(paper) for paper in papers],
        page=page,
        page_size=page_size,
        total=total,
        digest_status=_digest_status(db),
    )


def _get_paper_or_404(db: Session, arxiv_id: str) -> Paper:
    base_id, _version = normalize_arxiv_id(arxiv_id)
    paper = (
        db.query(Paper)
        .options(joinedload(Paper.breakdown))
        .filter(Paper.arxiv_id.in_([arxiv_id, base_id]))
        .one_or_none()
    )
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _resolve_synthesis_papers(db: Session, payload: SynthesisRunIn) -> list[Paper]:
    if payload.paper_ids is not None:
        requested_ids = _unique_ints(payload.paper_ids)
        if len(requested_ids) < 2:
            raise HTTPException(status_code=400, detail="Select at least 2 unique papers for synthesis")
        if len(requested_ids) > MAX_SYNTHESIS_PAPERS:
            raise HTTPException(status_code=400, detail=f"Select at most {MAX_SYNTHESIS_PAPERS} papers")

        papers = db.query(Paper).options(joinedload(Paper.breakdown)).filter(Paper.id.in_(requested_ids)).all()
        papers_by_id = {paper.id: paper for paper in papers}
        missing = [paper_id for paper_id in requested_ids if paper_id not in papers_by_id]
        if missing:
            raise HTTPException(status_code=400, detail=f"Selected papers not found: {missing}")
        return [papers_by_id[paper_id] for paper_id in requested_ids]

    requested_arxiv_ids = _unique_arxiv_ids(payload.arxiv_ids or [])
    if len(requested_arxiv_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 unique papers for synthesis")
    if len(requested_arxiv_ids) > MAX_SYNTHESIS_PAPERS:
        raise HTTPException(status_code=400, detail=f"Select at most {MAX_SYNTHESIS_PAPERS} papers")

    papers = db.query(Paper).options(joinedload(Paper.breakdown)).filter(Paper.arxiv_id.in_(requested_arxiv_ids)).all()
    papers_by_arxiv_id = {paper.arxiv_id: paper for paper in papers}
    missing = [arxiv_id for arxiv_id in requested_arxiv_ids if arxiv_id not in papers_by_arxiv_id]
    if missing:
        raise HTTPException(status_code=400, detail=f"Selected papers not found: {missing}")
    return [papers_by_arxiv_id[arxiv_id] for arxiv_id in requested_arxiv_ids]


def _unique_ints(values: list[int]) -> list[int]:
    seen: set[int] = set()
    unique_values: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _unique_arxiv_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        base_id, _version = normalize_arxiv_id(value.strip())
        if not base_id or base_id in seen:
            continue
        seen.add(base_id)
        unique_values.append(base_id)
    return unique_values


def _search_cache_inputs(q: str | None, label_type: str | None, label: str | None) -> tuple[str, str, str]:
    return (
        _normalize_search_text(q or ""),
        _clean_search_filter(label_type) or "",
        _clean_search_filter(label) or "",
    )


def _get_search_cache_entry(
    db: Session,
    normalized_q: str,
    normalized_label_type: str,
    normalized_label: str,
    limit: int,
) -> RetrievalSearchCache | None:
    return (
        db.query(RetrievalSearchCache)
        .filter(
            RetrievalSearchCache.normalized_q == normalized_q,
            RetrievalSearchCache.normalized_label_type == normalized_label_type,
            RetrievalSearchCache.normalized_label == normalized_label,
            RetrievalSearchCache.limit == limit,
            RetrievalSearchCache.cache_version == RETRIEVAL_SEARCH_CACHE_VERSION,
        )
        .one_or_none()
    )


def _store_search_cache_entry(
    db: Session,
    normalized_q: str,
    normalized_label_type: str,
    normalized_label: str,
    limit: int,
    response: SearchResponse,
) -> None:
    cached = RetrievalSearchCache(
        normalized_q=normalized_q,
        normalized_label_type=normalized_label_type,
        normalized_label=normalized_label,
        limit=limit,
        cache_version=RETRIEVAL_SEARCH_CACHE_VERSION,
        response_json=response.model_dump_json(),
        result_count=response.total,
    )
    db.add(cached)
    db.commit()


def _search_cache_status(db: Session) -> SearchCacheStatusOut:
    entries = (
        db.query(RetrievalSearchCache)
        .filter(RetrievalSearchCache.cache_version == RETRIEVAL_SEARCH_CACHE_VERSION)
        .order_by(RetrievalSearchCache.updated_at.desc(), RetrievalSearchCache.id.desc())
        .limit(50)
        .all()
    )
    total_entries = (
        db.query(RetrievalSearchCache)
        .filter(RetrievalSearchCache.cache_version == RETRIEVAL_SEARCH_CACHE_VERSION)
        .count()
    )
    total_hits = int(
        db.query(func.coalesce(func.sum(RetrievalSearchCache.hit_count), 0))
        .filter(RetrievalSearchCache.cache_version == RETRIEVAL_SEARCH_CACHE_VERSION)
        .scalar()
        or 0
    )
    return SearchCacheStatusOut(
        cache_version=RETRIEVAL_SEARCH_CACHE_VERSION,
        total_entries=total_entries,
        total_hits=total_hits,
        entries=[_search_cache_entry_to_schema(entry) for entry in entries],
    )


def _delete_search_cache_entries(db: Session, cache_id: int | None = None) -> SearchCacheDeleteResponse:
    query = db.query(RetrievalSearchCache).filter(
        RetrievalSearchCache.cache_version == RETRIEVAL_SEARCH_CACHE_VERSION,
    )
    if cache_id is not None:
        query = query.filter(RetrievalSearchCache.id == cache_id)

    deleted_count = query.delete(synchronize_session=False)
    if cache_id is not None and deleted_count == 0:
        db.rollback()
        raise HTTPException(status_code=404, detail="Search cache entry not found")

    db.commit()
    return SearchCacheDeleteResponse(
        cache_version=RETRIEVAL_SEARCH_CACHE_VERSION,
        deleted_count=deleted_count,
    )


def _search_cache_entry_to_schema(entry: RetrievalSearchCache) -> SearchCacheEntryOut:
    return SearchCacheEntryOut(
        id=entry.id,
        normalized_q=entry.normalized_q,
        normalized_label_type=entry.normalized_label_type,
        normalized_label=entry.normalized_label,
        limit=entry.limit,
        cache_version=entry.cache_version,
        result_count=entry.result_count,
        hit_count=entry.hit_count,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        last_hit_at=entry.last_hit_at,
    )


def _search_papers(
    db: Session,
    q: str | None,
    label_type: str | None,
    label: str | None,
    limit: int,
) -> list[SearchResultOut]:
    query_terms = _search_terms(q)
    label_type_filter = _clean_search_filter(label_type)
    label_filter = _clean_search_filter(label)

    if not query_terms and not label_type_filter and not label_filter:
        return []

    papers = (
        db.query(Paper)
        .options(joinedload(Paper.breakdown), joinedload(Paper.classifications))
        .order_by(Paper.score.desc().nullslast(), Paper.published_at.desc())
        .all()
    )
    results: list[SearchResultOut] = []
    for paper in papers:
        classifications = list(paper.classifications)
        if (label_type_filter or label_filter) and not _classification_filter_matches(
            classifications, label_type_filter, label_filter
        ):
            continue

        matched_fields = _matched_paper_fields(paper, query_terms)
        matched_labels = _matched_classification_labels(
            classifications=classifications,
            query_terms=query_terms,
            label_type_filter=label_type_filter,
            label_filter=label_filter,
        )
        if query_terms and not matched_fields and not matched_labels:
            continue

        score = _search_score(paper=paper, matched_fields=matched_fields, matched_labels=matched_labels)
        results.append(
            SearchResultOut(
                paper=_paper_to_schema(paper),
                score=score,
                matched_fields=matched_fields,
                matched_labels=matched_labels,
                reason=_search_reason(matched_fields=matched_fields, matched_labels=matched_labels),
            )
        )

    return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


def _classification_run_papers(db: Session, limit: int | None, only_missing: bool) -> list[Paper]:
    query = (
        db.query(Paper)
        .options(joinedload(Paper.breakdown))
        .filter(Paper.is_summarized.is_(True))
        .order_by(Paper.published_at.desc(), Paper.id.asc())
    )
    if only_missing:
        classified_paper_ids = db.query(PaperClassification.paper_id)
        query = query.filter(~Paper.id.in_(classified_paper_ids))
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def _classification_status(db: Session) -> ClassificationStatusOut:
    summarized_paper_count = db.query(Paper).filter(Paper.is_summarized.is_(True)).count()
    label_type_counts = {label_type: 0 for label_type in LABEL_TYPES}

    rows = (
        db.query(PaperClassification.label_type, func.count(PaperClassification.id))
        .join(Paper, PaperClassification.paper_id == Paper.id)
        .filter(Paper.is_summarized.is_(True))
        .group_by(PaperClassification.label_type)
        .all()
    )
    for label_type, count in rows:
        label_type_counts[str(label_type)] = int(count or 0)

    classified_paper_count = int(
        db.query(func.count(func.distinct(PaperClassification.paper_id)))
        .join(Paper, PaperClassification.paper_id == Paper.id)
        .filter(Paper.is_summarized.is_(True))
        .scalar()
        or 0
    )
    coverage_percentage = (
        round((classified_paper_count / summarized_paper_count) * 100, 2) if summarized_paper_count else 0.0
    )
    return ClassificationStatusOut(
        label_type_counts=label_type_counts,
        classified_paper_count=classified_paper_count,
        summarized_paper_count=summarized_paper_count,
        coverage_percentage=coverage_percentage,
        total_labels=sum(label_type_counts.values()),
    )


def _search_terms(q: str | None) -> list[str]:
    if not q:
        return []
    return [term for term in _normalize_search_text(q).split() if term]


def _clean_search_filter(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _normalize_search_text(value)
    return cleaned or None


def _normalize_search_text(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _classification_filter_matches(
    classifications: list[PaperClassification],
    label_type_filter: str | None,
    label_filter: str | None,
) -> bool:
    for classification in classifications:
        label_type = _normalize_search_text(classification.label_type)
        label = _normalize_search_text(classification.label)
        if label_type_filter and label_type_filter not in label_type:
            continue
        if label_filter and label_filter not in label:
            continue
        return True
    return False


def _matched_paper_fields(paper: Paper, query_terms: list[str]) -> list[str]:
    if not query_terms:
        return []

    fields = _paper_search_fields(paper)
    return [
        field_name
        for field_name, value in fields.items()
        if all(term in _normalize_search_text(value) for term in query_terms)
    ]


def _paper_search_fields(paper: Paper) -> dict[str, str]:
    fields = {
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": " ".join(str(author) for author in _json_list(paper.authors_json)),
        "category": " ".join(
            [paper.primary_category, *[str(category) for category in _json_list(paper.categories_json)]]
        ),
    }
    if paper.breakdown is not None:
        fields.update(
            {
                "takeaway": paper.breakdown.one_line_takeaway,
                "summary": paper.breakdown.simple_summary,
                "context": paper.breakdown.context,
                "mechanism": paper.breakdown.mechanism,
                "evidence": paper.breakdown.evidence,
                "caveats": " ".join(str(item) for item in _json_list(paper.breakdown.methodology_caveats_json)),
                "extensions": " ".join(str(item) for item in _json_list(paper.breakdown.meaningful_extensions_json)),
                "tags": " ".join(str(item) for item in _json_list(paper.breakdown.tags_json)),
                "questions": " ".join(str(item) for item in _json_list(paper.breakdown.follow_up_questions_json)),
            }
        )
    return fields


def _matched_classification_labels(
    classifications: list[PaperClassification],
    query_terms: list[str],
    label_type_filter: str | None,
    label_filter: str | None,
) -> list[str]:
    matched_labels: list[str] = []
    for classification in classifications:
        label_type = _normalize_search_text(classification.label_type)
        label = _normalize_search_text(classification.label)
        rationale = _normalize_search_text(classification.rationale or "")
        label_type_matches = not label_type_filter or label_type_filter in label_type
        label_matches = not label_filter or label_filter in label
        query_matches = not query_terms or all(
            term in label or term in label_type or term in rationale for term in query_terms
        )
        if label_type_matches and label_matches and query_matches:
            matched_labels.append(f"{classification.label_type}: {classification.label}")
    return sorted(set(matched_labels))


def _search_score(paper: Paper, matched_fields: list[str], matched_labels: list[str]) -> float:
    base_score = float(paper.score or 0.0) / 100
    field_score = len(matched_fields) * 0.25
    label_score = len(matched_labels) * 0.35
    title_bonus = 0.5 if "title" in matched_fields else 0.0
    return round(base_score + field_score + label_score + title_bonus, 3)


def _search_reason(matched_fields: list[str], matched_labels: list[str]) -> str:
    parts: list[str] = []
    if matched_fields:
        parts.append(f"Matched paper fields: {', '.join(matched_fields)}")
    if matched_labels:
        parts.append(f"Matched ontology labels: {', '.join(matched_labels)}")
    return "; ".join(parts) if parts else "Matched retrieval index."


def _paper_to_schema(paper: Paper) -> PaperWithBreakdown:
    return PaperWithBreakdown(
        id=paper.id,
        arxiv_id=paper.arxiv_id,
        arxiv_version=paper.arxiv_version,
        title=paper.title,
        abstract=paper.abstract,
        authors=json.loads(paper.authors_json),
        primary_category=paper.primary_category,
        categories=json.loads(paper.categories_json),
        published_at=paper.published_at,
        updated_at=paper.updated_at,
        arxiv_url=paper.arxiv_url,
        pdf_url=paper.pdf_url,
        is_summarized=paper.is_summarized,
        is_saved=paper.is_saved,
        score=paper.score,
        breakdown=_breakdown_to_schema(paper.breakdown) if paper.breakdown else None,
    )


def _breakdown_to_schema(breakdown: PaperBreakdown) -> PaperBreakdownOut:
    return PaperBreakdownOut(
        one_line_takeaway=breakdown.one_line_takeaway,
        simple_summary=breakdown.simple_summary,
        context=breakdown.context,
        what_is_new=breakdown.what_is_new,
        mechanism=breakdown.mechanism,
        evidence=breakdown.evidence,
        methodology_caveats=json.loads(breakdown.methodology_caveats_json),
        meaningful_extensions=json.loads(breakdown.meaningful_extensions_json),
        novelty_type=breakdown.novelty_type,
        difficulty=breakdown.difficulty,
        confidence=breakdown.confidence,
        read_this_if=breakdown.read_this_if,
        tags=json.loads(breakdown.tags_json),
        vibe=breakdown.vibe,
        glossary=json.loads(breakdown.glossary_json),
        follow_up_questions=json.loads(breakdown.follow_up_questions_json),
        model_provider=breakdown.model_provider,
        model_name=breakdown.model_name,
        source_basis=breakdown.source_basis,
        created_at=breakdown.created_at,
    )


def _paper_classifications_to_schema(
    paper: Paper, classifications: list[PaperClassification]
) -> PaperClassificationsResponse:
    return PaperClassificationsResponse(
        paper_id=paper.id,
        arxiv_id=paper.arxiv_id,
        items=[_classification_to_schema(classification) for classification in classifications],
    )


def _classification_to_schema(classification: PaperClassification) -> PaperClassificationOut:
    return PaperClassificationOut(
        id=classification.id,
        paper_id=classification.paper_id,
        label_type=classification.label_type,
        label=classification.label,
        confidence=classification.confidence,
        source=classification.source,
        rationale=classification.rationale,
        created_at=classification.created_at,
        updated_at=classification.updated_at,
    )


def _synthesis_run_detail_to_schema(db: Session, run: SynthesisRun) -> SynthesisRunDetailOut:
    selected_papers = _synthesis_run_papers(db, run.id)
    return SynthesisRunDetailOut(
        **_synthesis_run_to_summary(run).model_dump(),
        selected_papers=[_paper_to_schema(paper) for paper in selected_papers],
        argument_map=_json_list(run.argument_map_json),
        contradictions=_json_list(run.contradictions_json),
        evidence_matrix=_json_list(run.evidence_matrix_json),
        open_questions=_json_list(run.open_questions_json),
        extension_ideas=_json_list(run.extension_ideas_json),
        replication_or_ablation_plan=_json_list(run.replication_or_ablation_plan_json),
        caveats=_json_list(run.caveats_json),
    )


def _synthesis_run_to_summary(run: SynthesisRun) -> SynthesisRunSummaryOut:
    source_paper_ids = _run_source_paper_ids(run)
    return SynthesisRunSummaryOut(
        id=run.id,
        mode=run.mode,
        instructions=run.instructions,
        selected_paper_count=len(source_paper_ids),
        source_paper_ids=source_paper_ids,
        prompt_version=run.prompt_version or SYNTHESIS_PROMPT_VERSION,
        model_provider=run.model_provider or SYNTHESIS_MODEL_PROVIDER,
        model_name=run.model_name or SYNTHESIS_MODEL_NAME,
        created_at=run.created_at,
    )


def _synthesis_run_papers(db: Session, run_id: int) -> list[Paper]:
    rows = (
        db.query(SynthesisRunPaper)
        .options(joinedload(SynthesisRunPaper.paper).joinedload(Paper.breakdown))
        .filter(SynthesisRunPaper.run_id == run_id)
        .order_by(SynthesisRunPaper.position.asc(), SynthesisRunPaper.paper_id.asc())
        .all()
    )
    return [row.paper for row in rows]


def _run_source_paper_ids(run: SynthesisRun) -> list[int]:
    return [int(paper_id) for paper_id in _json_list(run.source_paper_ids_json)]


def _normalize_category_scope(category_scope: list[str] | None) -> list[str] | None:
    if category_scope is None:
        return None
    return [category.strip() for category in category_scope if category.strip()]


def _create_digest_job(db: Session, payload: DigestRunIn) -> DigestRun:
    category_scope = _normalize_category_scope(payload.category_scope)
    if payload.category_scope is not None and not category_scope:
        raise HTTPException(status_code=400, detail="category_scope must include at least one non-empty category")

    categories = category_scope or settings.category_list
    run = DigestRun(
        target_date=payload.target_date,
        category_scope_json=json.dumps(categories),
        status="pending",
        config_json=json.dumps(
            {
                "categories": categories,
                "lookback_hours": settings.lookback_hours,
                "top_n": settings.top_n,
                "full_text_top_k": settings.full_text_top_k,
                "target_date": payload.target_date.isoformat() if payload.target_date else None,
            }
        ),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _digest_status(db: Session) -> DigestStatusOut:
    latest = db.query(DigestRun).order_by(DigestRun.started_at.desc()).first()
    today_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    summarized_today = db.query(PaperBreakdown).filter(PaperBreakdown.created_at >= today_start).count()
    return DigestStatusOut(
        last_run_at=latest.started_at if latest else None,
        status=latest.status if latest else "idle",
        papers_summarized_today=summarized_today,
        error_message=latest.error_message if latest else None,
    )


def _run_to_schema(run: DigestRun | None) -> DigestRunOut | None:
    if run is None:
        return None
    return DigestRunOut(
        id=run.id,
        target_date=run.target_date,
        category_scope=_run_category_scope(run),
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        papers_fetched=run.papers_fetched,
        papers_new=run.papers_new,
        papers_summarized=run.papers_summarized,
        error_message=run.error_message,
    )


def _run_detail_to_schema(db: Session, run: DigestRun) -> DigestRunDetailOut:
    llm_calls = (
        db.query(LLMCall)
        .filter(LLMCall.digest_run_id == run.id)
        .order_by(LLMCall.created_at.asc(), LLMCall.id.asc())
        .all()
    )
    paper_ids = [call.paper_id for call in llm_calls if call.paper_id is not None]
    papers_by_id = {}
    if paper_ids:
        papers_by_id = {paper.id: paper for paper in db.query(Paper).filter(Paper.id.in_(paper_ids)).all()}

    base = _run_to_schema(run)
    return DigestRunDetailOut(
        **base.model_dump(),
        config=_json_dict(run.config_json),
        llm_calls=[_llm_call_to_schema(call, papers_by_id.get(call.paper_id)) for call in llm_calls],
        llm_tokens_total=sum(call.total_tokens for call in llm_calls),
        estimated_llm_cost_usd=round(sum(call.estimated_cost_usd for call in llm_calls), 6),
    )


def _record_synthesis_usage(db: Session, run: SynthesisRun, output: dict[str, object]) -> None:
    usage = output.get("_llm_usage")
    if not isinstance(usage, dict):
        return

    metadata = {
        "mode": run.mode,
        "prompt_version": run.prompt_version,
        "source_paper_ids": _run_source_paper_ids(run),
        "synthesis_validation_status": output.get("_synthesis_validation_status", "valid"),
    }
    if output.get("_synthesis_validation_error"):
        metadata["synthesis_validation_error"] = output["_synthesis_validation_error"]

    db.add(
        LLMCall(
            task=SYNTHESIS_TASK,
            provider=str(usage.get("provider", run.model_provider)),
            model_name=str(usage.get("model_name", run.model_name)),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            estimated_cost_usd=float(usage.get("estimated_cost_usd", 0.0) or 0.0),
            metadata_json=json.dumps(metadata),
        )
    )
    db.flush()


def _backfill_job_to_schema(job: BackfillJob, message: str | None = None) -> BackfillJobOut:
    estimated_cost = round(job.estimated_cost_usd or 0.0, 6)
    budget = round(job.budget_usd or 0.0, 6)
    return BackfillJobOut(
        id=job.id,
        start_date=job.start_date,
        end_date=job.end_date,
        category_scope=[str(category) for category in _json_list(job.category_scope_json)],
        status=job.status,
        budget_usd=budget,
        estimated_cost_usd=estimated_cost,
        budget_remaining_usd=round(max(budget - estimated_cost, 0.0), 6),
        total_days=job.total_days,
        completed_days=job.completed_days,
        failed_days=job.failed_days,
        papers_fetched=job.papers_fetched,
        papers_new=job.papers_new,
        papers_summarized=job.papers_summarized,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        message=message,
    )


def _date_range(start_date: date, end_date: date) -> Iterator[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _backfill_date_succeeded(db: Session, job_id: int, target_date: date) -> bool:
    return (
        db.query(DigestRun.id)
        .filter(
            DigestRun.backfill_job_id == job_id,
            DigestRun.target_date == target_date,
            DigestRun.status == "success",
        )
        .first()
        is not None
    )


def _next_backfill_date(db: Session, job: BackfillJob) -> date | None:
    for target_date in _date_range(job.start_date, job.end_date):
        if not _backfill_date_succeeded(db, job.id, target_date):
            return target_date
    return None


def _backfill_budget_exhausted(job: BackfillJob) -> bool:
    return (job.budget_usd or 0.0) <= (job.estimated_cost_usd or 0.0)


def _finish_backfill_job(
    db: Session,
    job: BackfillJob,
    status_name: BackfillStatusName,
    error_message: str | None,
) -> None:
    job.status = status_name
    job.completed_at = datetime.now(UTC)
    job.error_message = error_message
    _sync_backfill_job_metrics(db, job)
    db.commit()
    db.refresh(job)


def _sync_backfill_job_metrics(db: Session, job: BackfillJob) -> None:
    runs = db.query(DigestRun).filter(DigestRun.backfill_job_id == job.id).all()
    successful_dates = {
        run.target_date
        for run in runs
        if run.target_date is not None and job.start_date <= run.target_date <= job.end_date and run.status == "success"
    }
    failed_dates = {
        run.target_date
        for run in runs
        if run.target_date is not None
        and job.start_date <= run.target_date <= job.end_date
        and run.status == "failed"
        and run.target_date not in successful_dates
    }
    job.completed_days = len(successful_dates)
    job.failed_days = len(failed_dates)
    job.papers_fetched = sum(run.papers_fetched or 0 for run in runs)
    job.papers_new = sum(run.papers_new or 0 for run in runs)
    job.papers_summarized = sum(run.papers_summarized or 0 for run in runs)
    job.estimated_cost_usd = round(_backfill_estimated_cost(db, job.id), 6)
    db.flush()


def _backfill_estimated_cost(db: Session, job_id: int) -> float:
    value = (
        db.query(func.coalesce(func.sum(LLMCall.estimated_cost_usd), 0.0))
        .join(DigestRun, LLMCall.digest_run_id == DigestRun.id)
        .filter(DigestRun.backfill_job_id == job_id)
        .scalar()
    )
    return float(value or 0.0)


def _llm_call_to_schema(call: LLMCall, paper: Paper | None = None) -> LLMCallOut:
    return LLMCallOut(
        id=call.id,
        paper_id=call.paper_id,
        arxiv_id=paper.arxiv_id if paper else None,
        paper_title=paper.title if paper else None,
        task=call.task,
        provider=call.provider,
        model_name=call.model_name,
        prompt_tokens=call.prompt_tokens,
        completion_tokens=call.completion_tokens,
        total_tokens=call.total_tokens,
        estimated_cost_usd=call.estimated_cost_usd,
        metadata=_json_dict(call.metadata_json),
        created_at=call.created_at,
    )


def _run_category_scope(run: DigestRun) -> list[str]:
    category_scope = _json_list(run.category_scope_json)
    if category_scope:
        return [str(category) for category in category_scope]

    config_categories = _json_dict(run.config_json).get("categories")
    if isinstance(config_categories, list):
        return [str(category) for category in config_categories]
    return []


def _json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _json_dump(value: object) -> str:
    return json.dumps(value, sort_keys=True)
