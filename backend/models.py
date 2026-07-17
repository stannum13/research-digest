from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arxiv_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    arxiv_version: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    abstract: Mapped[str] = mapped_column(Text)
    authors_json: Mapped[str] = mapped_column(Text, default="[]")
    primary_category: Mapped[str] = mapped_column(String, index=True)
    categories_json: Mapped[str] = mapped_column(Text, default="[]")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    arxiv_url: Mapped[str] = mapped_column(String)
    pdf_url: Mapped[str] = mapped_column(String)
    raw_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_local_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_summarized: Mapped[bool] = mapped_column(Boolean, default=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    breakdown: Mapped["PaperBreakdown | None"] = relationship(
        back_populates="paper", cascade="all, delete-orphan", uselist=False
    )
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    classifications: Mapped[list["PaperClassification"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    synthesis_runs: Mapped[list["SynthesisRunPaper"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class PaperBreakdown(Base):
    __tablename__ = "paper_breakdowns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    one_line_takeaway: Mapped[str] = mapped_column(Text)
    simple_summary: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    what_is_new: Mapped[str] = mapped_column(Text)
    mechanism: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    methodology_caveats_json: Mapped[str] = mapped_column(Text, default="[]")
    meaningful_extensions_json: Mapped[str] = mapped_column(Text, default="[]")
    novelty_type: Mapped[str] = mapped_column(String)
    difficulty: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[str] = mapped_column(String)
    read_this_if: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    vibe: Mapped[str] = mapped_column(String)
    glossary_json: Mapped[str] = mapped_column(Text, default="[]")
    follow_up_questions_json: Mapped[str] = mapped_column(Text, default="[]")
    model_provider: Mapped[str] = mapped_column(String, default="mock")
    model_name: Mapped[str] = mapped_column(String, default="seed-editor")
    source_basis: Mapped[str] = mapped_column(String, default="abstract_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="breakdown")


class PaperSummaryCache(Base):
    __tablename__ = "paper_summary_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_arxiv_id: Mapped[str] = mapped_column(String, index=True)
    paper_arxiv_version: Mapped[str] = mapped_column(String, default="")
    content_hash: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    model_name: Mapped[str] = mapped_column(String, index=True)
    task: Mapped[str] = mapped_column(String, default="paper_summary", index=True)
    prompt_version: Mapped[str] = mapped_column(String, index=True)
    result_json: Mapped[str] = mapped_column(Text)
    source_basis: Mapped[str] = mapped_column(String, default="abstract_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RetrievalSearchCache(Base):
    __tablename__ = "retrieval_search_cache"
    __table_args__ = (
        UniqueConstraint(
            "normalized_q",
            "normalized_label_type",
            "normalized_label",
            "limit",
            "cache_version",
            name="ux_retrieval_search_cache_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_q: Mapped[str] = mapped_column(String, default="", index=True)
    normalized_label_type: Mapped[str] = mapped_column(String, default="", index=True)
    normalized_label: Mapped[str] = mapped_column(String, default="", index=True)
    limit: Mapped[int] = mapped_column(Integer)
    cache_version: Mapped[str] = mapped_column(String, index=True)
    response_json: Mapped[str] = mapped_column(Text)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaperClassification(Base):
    __tablename__ = "paper_classifications"
    __table_args__ = (UniqueConstraint("paper_id", "label_type", "label", name="ux_paper_classifications_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    label_type: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String, default="metadata-breakdown-heuristic-v1", index=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="classifications")


class SynthesisRun(Base):
    __tablename__ = "synthesis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    argument_map_json: Mapped[str] = mapped_column(Text, default="[]")
    contradictions_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_matrix_json: Mapped[str] = mapped_column(Text, default="[]")
    open_questions_json: Mapped[str] = mapped_column(Text, default="[]")
    extension_ideas_json: Mapped[str] = mapped_column(Text, default="[]")
    replication_or_ablation_plan_json: Mapped[str] = mapped_column(Text, default="[]")
    caveats_json: Mapped[str] = mapped_column(Text, default="[]")
    source_paper_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_version: Mapped[str] = mapped_column(String, default="synthesis-workbench-deterministic-v1")
    model_provider: Mapped[str] = mapped_column(String, default="none")
    model_name: Mapped[str] = mapped_column(String, default="metadata-breakdown-heuristic-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    selected_papers: Mapped[list["SynthesisRunPaper"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SynthesisRunPaper(Base):
    __tablename__ = "synthesis_run_papers"

    run_id: Mapped[int] = mapped_column(ForeignKey("synthesis_runs.id"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True, index=True)
    position: Mapped[int] = mapped_column(Integer)

    run: Mapped[SynthesisRun] = relationship(back_populates="selected_papers")
    paper: Mapped[Paper] = relationship(back_populates="synthesis_runs")


class DigestRun(Base):
    __tablename__ = "digest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backfill_job_id: Mapped[int | None] = mapped_column(ForeignKey("backfill_jobs.id"), nullable=True, index=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    category_scope_json: Mapped[str] = mapped_column(Text, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="running", index=True)
    papers_fetched: Mapped[int] = mapped_column(Integer, default=0)
    papers_new: Mapped[int] = mapped_column(Integer, default=0)
    papers_summarized: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")

    backfill_job: Mapped["BackfillJob | None"] = relationship(back_populates="digest_runs")
    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="digest_run", cascade="all, delete-orphan")


class BackfillJob(Base):
    __tablename__ = "backfill_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    category_scope_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    budget_usd: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    completed_days: Mapped[int] = mapped_column(Integer, default=0)
    failed_days: Mapped[int] = mapped_column(Integer, default=0)
    papers_fetched: Mapped[int] = mapped_column(Integer, default=0)
    papers_new: Mapped[int] = mapped_column(Integer, default=0)
    papers_summarized: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    digest_runs: Mapped[list[DigestRun]] = relationship(back_populates="backfill_job")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    signal: Mapped[str] = mapped_column(String, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="feedback")


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_run_id: Mapped[int | None] = mapped_column(ForeignKey("digest_runs.id"), nullable=True, index=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)
    task: Mapped[str] = mapped_column(String, default="paper_summary", index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    model_name: Mapped[str] = mapped_column(String, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    digest_run: Mapped[DigestRun | None] = relationship(back_populates="llm_calls")


class Preferences(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_weights_json: Mapped[str] = mapped_column(Text, default="{}")
    muted_terms_json: Mapped[str] = mapped_column(Text, default="[]")
    boosted_terms_json: Mapped[str] = mapped_column(Text, default="[]")
    category_weights_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


Index("ix_papers_category_score", Paper.primary_category, Paper.score)
Index("ix_digest_runs_started_status", DigestRun.started_at, DigestRun.status)
Index("ix_backfill_jobs_created_status", BackfillJob.created_at, BackfillJob.status)
Index("ix_synthesis_runs_created_mode", SynthesisRun.created_at, SynthesisRun.mode)
Index("ix_synthesis_run_papers_run_position", SynthesisRunPaper.run_id, SynthesisRunPaper.position)
Index("ix_paper_classifications_paper_type", PaperClassification.paper_id, PaperClassification.label_type)
Index(
    "ix_retrieval_search_cache_key",
    RetrievalSearchCache.normalized_q,
    RetrievalSearchCache.normalized_label_type,
    RetrievalSearchCache.normalized_label,
    RetrievalSearchCache.limit,
    RetrievalSearchCache.cache_version,
)
Index(
    "ux_paper_summary_cache_key",
    PaperSummaryCache.paper_arxiv_id,
    PaperSummaryCache.paper_arxiv_version,
    PaperSummaryCache.content_hash,
    PaperSummaryCache.provider,
    PaperSummaryCache.model_name,
    PaperSummaryCache.task,
    PaperSummaryCache.prompt_version,
    unique=True,
)
