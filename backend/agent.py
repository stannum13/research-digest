import json
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from arxiv_client import ArxivClient, ArxivPaper
from fulltext import extract_full_text
from models import DigestRun, LLMCall, Paper, PaperBreakdown, PaperSummaryCache
from ranking import RankablePaper, score_paper, select_diverse_top
from settings import Settings
from summarizer import (
    PAPER_SUMMARY_TASK,
    SUMMARY_PROMPT_VERSION,
    Summarizer,
    cacheable_summary_payload,
    get_summarizer,
    paper_summary_content_hash,
    prepare_summary_output,
)


def run_digest(
    db: Session,
    settings: Settings,
    target_date: date | None = None,
    category_scope: Sequence[str] | None = None,
    backfill_job_id: int | None = None,
    run_id: int | None = None,
) -> DigestRun:
    run = _prepare_run(
        db=db,
        settings=settings,
        target_date=target_date,
        category_scope=category_scope,
        backfill_job_id=backfill_job_id,
        run_id=run_id,
    )
    categories = _run_categories(run, settings)
    target_date = run.target_date

    try:
        if not settings.llm_configured:
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error_message = settings.llm_setup_hint
            db.commit()
            db.refresh(run)
            return run

        client = ArxivClient(settings)
        fetched = (
            client.fetch_for_date(target_date, categories=categories)
            if target_date
            else client.fetch_recent(categories=categories)
        )
        run.papers_fetched = len(fetched)
        fetched_ids = {paper.arxiv_id for paper in fetched}
        new_count = _store_candidates(db, fetched)
        run.papers_new = new_count

        rankable = [
            RankablePaper(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                abstract=paper.abstract,
                primary_category=paper.primary_category,
                categories=json.loads(paper.categories_json),
            )
            for paper in db.query(Paper).filter(Paper.is_summarized.is_(False), Paper.arxiv_id.in_(fetched_ids)).all()
        ]
        shortlist = select_diverse_top(rankable, settings.top_n)
        shortlist_ids = {paper.arxiv_id for paper in shortlist}
        summarizer = get_summarizer(settings)
        model_provider, model_name = _summarizer_identity(summarizer, settings)
        summarized = 0
        budget_exhausted = False

        for paper in db.query(Paper).filter(Paper.arxiv_id.in_(shortlist_ids)).all():
            if paper.breakdown:
                continue
            extracted = extract_full_text(paper.pdf_url)
            arxiv_paper = _paper_to_arxiv_paper(paper)
            content_hash = paper_summary_content_hash(arxiv_paper, extracted.text)
            cached_data = _cached_summary_data(
                db=db,
                paper=paper,
                content_hash=content_hash,
                provider=model_provider,
                model_name=model_name,
            )
            if cached_data is not None:
                _attach_breakdown(db, paper, cached_data)
                paper.is_summarized = True
                summarized += 1
                continue

            if settings.llm_run_budget_usd > 0 and _run_cost(db, run.id) >= settings.llm_run_budget_usd:
                run.error_message = f"LLM run budget reached before all shortlisted papers were summarized (${settings.llm_run_budget_usd:.2f})."
                budget_exhausted = True
                break

            raw_data = summarizer.summarize(arxiv_paper, extracted.text)
            repairer = getattr(summarizer, "repair_summary", None)
            prepared = prepare_summary_output(
                raw_data,
                arxiv_paper,
                extracted.text,
                repairer=repairer if callable(repairer) else None,
            )
            data = prepared.data
            _attach_breakdown(db, paper, data)
            if prepared.cacheable:
                _store_summary_cache(
                    db=db,
                    paper=paper,
                    content_hash=content_hash,
                    provider=model_provider,
                    model_name=model_name,
                    data=data,
                )
            _record_llm_usage(
                db,
                run.id,
                paper.id,
                data,
                provider=model_provider,
                model_name=model_name,
                content_hash=content_hash,
                validation_status=prepared.validation_status,
                validation_error=prepared.validation_error,
            )
            paper.is_summarized = True
            summarized += 1

        run.papers_summarized = summarized
        run.status = "budget_exhausted" if budget_exhausted else "success"
        run.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        db.rollback()
        run = db.get(DigestRun, run.id)
        if run is not None:
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error_message = str(exc)
            db.commit()
            db.refresh(run)
            return run
        raise


def _prepare_run(
    db: Session,
    settings: Settings,
    target_date: date | None,
    category_scope: Sequence[str] | None,
    backfill_job_id: int | None,
    run_id: int | None,
) -> DigestRun:
    categories = _normalize_category_scope(category_scope)
    if run_id is None:
        categories = categories or settings.category_list
        run = DigestRun(
            backfill_job_id=backfill_job_id,
            target_date=target_date,
            category_scope_json=json.dumps(categories),
            status="running",
            config_json=_run_config_json(settings=settings, categories=categories, target_date=target_date),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    run = db.get(DigestRun, run_id)
    if run is None:
        raise ValueError(f"Digest run {run_id} not found")

    categories = categories or _stored_categories(run) or settings.category_list
    run.backfill_job_id = backfill_job_id if backfill_job_id is not None else run.backfill_job_id
    run.target_date = target_date if target_date is not None else run.target_date
    run.category_scope_json = json.dumps(categories)
    run.status = "running"
    run.started_at = datetime.now(UTC)
    run.completed_at = None
    run.error_message = None
    run.papers_fetched = 0
    run.papers_new = 0
    run.papers_summarized = 0
    run.config_json = _run_config_json(settings=settings, categories=categories, target_date=run.target_date)
    db.commit()
    db.refresh(run)
    return run


def _run_config_json(settings: Settings, categories: Sequence[str], target_date: date | None) -> str:
    return json.dumps(
        {
            "categories": list(categories),
            "lookback_hours": settings.lookback_hours,
            "top_n": settings.top_n,
            "full_text_top_k": settings.full_text_top_k,
            "target_date": target_date.isoformat() if target_date else None,
        }
    )


def _stored_categories(run: DigestRun) -> list[str]:
    try:
        data = json.loads(run.category_scope_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(category).strip() for category in data if str(category).strip()]


def _run_categories(run: DigestRun, settings: Settings) -> list[str]:
    return _stored_categories(run) or settings.category_list


def _normalize_category_scope(category_scope: Sequence[str] | None) -> list[str]:
    if category_scope is None:
        return []
    return [category.strip() for category in category_scope if category.strip()]


def _store_candidates(db: Session, papers: list[ArxivPaper]) -> int:
    new_count = 0
    for item in papers:
        existing = db.query(Paper).filter(Paper.arxiv_id == item.arxiv_id).one_or_none()
        if existing:
            existing.arxiv_version = item.arxiv_version
            existing.title = item.title
            existing.abstract = item.abstract
            existing.authors_json = json.dumps(item.authors)
            existing.primary_category = item.primary_category
            existing.categories_json = json.dumps(item.categories)
            existing.updated_at = item.updated_at
            existing.last_seen_at = datetime.now(UTC)
            existing.score = score_paper(
                RankablePaper(
                    arxiv_id=item.arxiv_id,
                    title=item.title,
                    abstract=item.abstract,
                    primary_category=item.primary_category,
                    categories=item.categories,
                )
            )
            continue
        db.add(
            Paper(
                arxiv_id=item.arxiv_id,
                arxiv_version=item.arxiv_version,
                title=item.title,
                abstract=item.abstract,
                authors_json=json.dumps(item.authors),
                primary_category=item.primary_category,
                categories_json=json.dumps(item.categories),
                published_at=item.published_at,
                updated_at=item.updated_at,
                arxiv_url=item.arxiv_url,
                pdf_url=item.pdf_url,
                raw_metadata_json=json.dumps(item.raw_metadata),
                score=score_paper(
                    RankablePaper(
                        arxiv_id=item.arxiv_id,
                        title=item.title,
                        abstract=item.abstract,
                        primary_category=item.primary_category,
                        categories=item.categories,
                    )
                ),
            )
        )
        new_count += 1
    db.commit()
    return new_count


def _attach_breakdown(db: Session, paper: Paper, data: dict) -> None:
    data = cacheable_summary_payload(data)
    breakdown = PaperBreakdown(
        paper_id=paper.id,
        one_line_takeaway=data["one_line_takeaway"],
        simple_summary=data["simple_summary"],
        context=data["context"],
        what_is_new=data["what_is_new"],
        mechanism=data["mechanism"],
        evidence=data["evidence"],
        methodology_caveats_json=json.dumps(data["methodology_caveats"]),
        meaningful_extensions_json=json.dumps(data["meaningful_extensions"]),
        novelty_type=data["novelty_type"],
        difficulty=data["difficulty"],
        confidence=data["confidence"],
        read_this_if=data["read_this_if"],
        tags_json=json.dumps(data["tags"]),
        vibe=data["vibe"],
        glossary_json=json.dumps(data["glossary"]),
        follow_up_questions_json=json.dumps(data["follow_up_questions"]),
        model_provider=data["model_provider"],
        model_name=data["model_name"],
        source_basis=data["source_basis"],
    )
    db.add(breakdown)


def _record_llm_usage(
    db: Session,
    run_id: int,
    paper_id: int,
    data: dict,
    provider: str | None = None,
    model_name: str | None = None,
    content_hash: str | None = None,
    validation_status: str | None = None,
    validation_error: str | None = None,
) -> None:
    usage = data.get("_llm_usage") or {}
    metadata = {
        "source_basis": data.get("source_basis", "abstract_only"),
        "prompt_version": SUMMARY_PROMPT_VERSION,
    }
    if content_hash:
        metadata["content_hash"] = content_hash
    if validation_status:
        metadata["summary_validation_status"] = validation_status
    if validation_error:
        metadata["summary_validation_error"] = validation_error
    if data.get("_summary_repair_attempted") is not None:
        metadata["summary_repair_attempted"] = bool(data.get("_summary_repair_attempted"))
    if data.get("_summary_repair_prompt_version"):
        metadata["summary_repair_prompt_version"] = data["_summary_repair_prompt_version"]
    if data.get("_summary_repair_error"):
        metadata["summary_repair_error"] = data["_summary_repair_error"]

    db.add(
        LLMCall(
            digest_run_id=run_id,
            paper_id=paper_id,
            task=PAPER_SUMMARY_TASK,
            provider=provider or usage.get("provider", data.get("model_provider", "unknown")),
            model_name=model_name or usage.get("model_name", data.get("model_name", "unknown")),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            estimated_cost_usd=float(usage.get("estimated_cost_usd", 0.0) or 0.0),
            metadata_json=json.dumps(metadata),
        )
    )
    db.flush()


def _cached_summary_data(
    db: Session,
    paper: Paper,
    content_hash: str,
    provider: str,
    model_name: str,
) -> dict | None:
    cached = _summary_cache_row(
        db=db,
        paper=paper,
        content_hash=content_hash,
        provider=provider,
        model_name=model_name,
    )
    if cached is None:
        return None

    try:
        return cacheable_summary_payload(json.loads(cached.result_json))
    except (json.JSONDecodeError, ValueError):
        db.delete(cached)
        db.flush()
        return None


def _store_summary_cache(
    db: Session,
    paper: Paper,
    content_hash: str,
    provider: str,
    model_name: str,
    data: dict,
) -> None:
    payload = cacheable_summary_payload(data)
    cached = _summary_cache_row(
        db=db,
        paper=paper,
        content_hash=content_hash,
        provider=provider,
        model_name=model_name,
    )
    if cached is None:
        db.add(
            PaperSummaryCache(
                paper_arxiv_id=paper.arxiv_id,
                paper_arxiv_version=paper.arxiv_version or "",
                content_hash=content_hash,
                provider=provider,
                model_name=model_name,
                task=PAPER_SUMMARY_TASK,
                prompt_version=SUMMARY_PROMPT_VERSION,
                result_json=json.dumps(payload, sort_keys=True),
                source_basis=payload["source_basis"],
            )
        )
    else:
        cached.result_json = json.dumps(payload, sort_keys=True)
        cached.source_basis = payload["source_basis"]
    db.flush()


def _summary_cache_row(
    db: Session,
    paper: Paper,
    content_hash: str,
    provider: str,
    model_name: str,
) -> PaperSummaryCache | None:
    return (
        db.query(PaperSummaryCache)
        .filter(
            PaperSummaryCache.paper_arxiv_id == paper.arxiv_id,
            PaperSummaryCache.paper_arxiv_version == (paper.arxiv_version or ""),
            PaperSummaryCache.content_hash == content_hash,
            PaperSummaryCache.provider == provider,
            PaperSummaryCache.model_name == model_name,
            PaperSummaryCache.task == PAPER_SUMMARY_TASK,
            PaperSummaryCache.prompt_version == SUMMARY_PROMPT_VERSION,
        )
        .one_or_none()
    )


def _summarizer_identity(summarizer: Summarizer, settings: Settings) -> tuple[str, str]:
    provider = getattr(summarizer, "provider", None) or settings.llm_provider
    model_name = getattr(summarizer, "model_name", None) or getattr(summarizer, "model", None)
    if model_name:
        return str(provider), str(model_name)
    if provider == "openai":
        return "openai", settings.openai_model
    if provider == "zai":
        return "zai", settings.zai_synthesis_model
    if provider == "anthropic":
        return "anthropic", settings.anthropic_model
    return str(provider), "unknown"


def _run_cost(db: Session, run_id: int) -> float:
    return sum(
        row[0] or 0.0 for row in db.query(LLMCall.estimated_cost_usd).filter(LLMCall.digest_run_id == run_id).all()
    )


def _paper_to_arxiv_paper(paper: Paper) -> ArxivPaper:
    return ArxivPaper(
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
        raw_metadata=json.loads(paper.raw_metadata_json),
    )
