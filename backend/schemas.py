from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NoveltyType = Literal[
    "method", "benchmark", "dataset", "theory", "systems", "empirical", "application", "survey", "other"
]
Difficulty = Literal["beginner", "intermediate", "expert"]
Confidence = Literal["low", "medium", "high"]
DigestStatusName = Literal["idle", "pending", "running", "success", "failed", "partial", "budget_exhausted"]
BackfillStatusName = Literal["pending", "running", "success", "failed", "budget_exhausted", "canceled"]
FeedbackSignal = Literal["more_like_this", "less_like_this", "important", "hide", "read_later"]
SynthesisMode = Literal["overview", "compare", "argument_map", "research_plan"]
ClassificationLabelType = Literal[
    "method_family",
    "evidence_type",
    "caveat_class",
    "task",
    "dataset_or_benchmark",
    "architecture_primitive",
    "probe_family",
]


class ApiError(BaseModel):
    error: str
    detail: str | None = None


class GlossaryTerm(BaseModel):
    term: str
    definition: str


class PaperBreakdownOut(BaseModel):
    one_line_takeaway: str
    simple_summary: str
    context: str
    what_is_new: str
    mechanism: str
    evidence: str
    methodology_caveats: list[str]
    meaningful_extensions: list[str]
    novelty_type: NoveltyType
    difficulty: Difficulty
    confidence: Confidence
    read_this_if: str
    tags: list[str]
    vibe: str
    glossary: list[GlossaryTerm]
    follow_up_questions: list[str]
    model_provider: str
    model_name: str
    source_basis: Literal["abstract_only", "partial_full_text", "full_text"]
    created_at: datetime


class PaperWithBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    arxiv_id: str
    arxiv_version: str | None = None
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    categories: list[str]
    published_at: datetime
    updated_at: datetime
    arxiv_url: str
    pdf_url: str
    is_summarized: bool
    is_saved: bool
    score: float | None = None
    breakdown: PaperBreakdownOut | None = None


class PaperClassificationOut(BaseModel):
    id: int
    paper_id: int
    label_type: ClassificationLabelType
    label: str
    confidence: float = Field(ge=0, le=1)
    source: str
    rationale: str
    created_at: datetime
    updated_at: datetime


class PaperClassificationsResponse(BaseModel):
    paper_id: int
    arxiv_id: str
    items: list[PaperClassificationOut]


class ClassificationStatusOut(BaseModel):
    label_type_counts: dict[str, int]
    classified_paper_count: int
    summarized_paper_count: int
    coverage_percentage: float
    total_labels: int


class ClassificationRunOut(BaseModel):
    only_missing: bool
    limit: int | None = None
    papers_processed: int
    paper_ids: list[int]
    arxiv_ids: list[str]
    status: ClassificationStatusOut


class DigestStatusOut(BaseModel):
    last_run_at: datetime | None = None
    status: DigestStatusName
    papers_summarized_today: int
    error_message: str | None = None


class PapersResponse(BaseModel):
    items: list[PaperWithBreakdown]
    page: int
    page_size: int
    total: int
    digest_status: DigestStatusOut


class SearchResultOut(BaseModel):
    paper: PaperWithBreakdown
    score: float
    matched_fields: list[str]
    matched_labels: list[str]
    reason: str


class SearchResponse(BaseModel):
    items: list[SearchResultOut]
    total: int
    query: str


class SearchCacheEntryOut(BaseModel):
    id: int
    normalized_q: str
    normalized_label_type: str
    normalized_label: str
    limit: int
    cache_version: str
    result_count: int
    hit_count: int
    created_at: datetime
    updated_at: datetime
    last_hit_at: datetime | None = None


class SearchCacheStatusOut(BaseModel):
    cache_version: str
    total_entries: int
    total_hits: int
    entries: list[SearchCacheEntryOut]


class SearchCacheDeleteResponse(BaseModel):
    cache_version: str
    deleted_count: int


class FeedbackIn(BaseModel):
    signal: FeedbackSignal
    note: str | None = Field(default=None, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    paper_id: int
    signal: FeedbackSignal
    note: str | None
    created_at: datetime


class SynthesisRunIn(BaseModel):
    paper_ids: list[int] | None = Field(default=None, min_length=1, max_length=8)
    arxiv_ids: list[str] | None = Field(default=None, min_length=1, max_length=8)
    mode: SynthesisMode = "overview"
    instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("instructions")
    @classmethod
    def normalize_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_identifier_shape(self) -> "SynthesisRunIn":
        if (self.paper_ids is None) == (self.arxiv_ids is None):
            raise ValueError("Provide exactly one of paper_ids or arxiv_ids")
        return self


class SynthesisRunSummaryOut(BaseModel):
    id: int
    mode: str
    instructions: str | None = None
    selected_paper_count: int
    source_paper_ids: list[int]
    prompt_version: str
    model_provider: str
    model_name: str
    created_at: datetime


class SynthesisRunDetailOut(SynthesisRunSummaryOut):
    selected_papers: list[PaperWithBreakdown]
    argument_map: list[dict[str, object]]
    contradictions: list[dict[str, object]]
    evidence_matrix: list[dict[str, object]]
    open_questions: list[dict[str, object]]
    extension_ideas: list[dict[str, object]]
    replication_or_ablation_plan: list[dict[str, object]]
    caveats: list[dict[str, object]]


class SynthesisRunsResponse(BaseModel):
    items: list[SynthesisRunSummaryOut]
    page: int
    page_size: int
    total: int


class DigestRunIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_date: date | None = None
    category_scope: list[str] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def accept_categories_alias(cls, data: object) -> object:
        return _accept_categories_alias(data)


class DigestRunOut(BaseModel):
    id: int
    target_date: date | None = None
    category_scope: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    papers_fetched: int
    papers_new: int
    papers_summarized: int
    error_message: str | None = None
    message: str | None = None


class DigestLatestResponse(BaseModel):
    run: DigestRunOut | None
    papers: list[PaperWithBreakdown]


class LLMCallOut(BaseModel):
    id: int
    paper_id: int | None = None
    arxiv_id: str | None = None
    paper_title: str | None = None
    task: str
    provider: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    metadata: dict
    created_at: datetime


class DigestRunDetailOut(DigestRunOut):
    config: dict
    llm_calls: list[LLMCallOut]
    llm_tokens_total: int
    estimated_llm_cost_usd: float


class BackfillJobIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date: date
    end_date: date
    category_scope: list[str] | None = Field(default=None, min_length=1, max_length=50)
    budget_usd: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def accept_categories_alias(cls, data: object) -> object:
        return _accept_categories_alias(data)

    @model_validator(mode="after")
    def validate_date_range(self) -> "BackfillJobIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class BackfillJobOut(BaseModel):
    id: int
    start_date: date
    end_date: date
    category_scope: list[str] = Field(default_factory=list)
    status: BackfillStatusName
    budget_usd: float
    estimated_cost_usd: float
    budget_remaining_usd: float
    total_days: int
    completed_days: int
    failed_days: int
    papers_fetched: int
    papers_new: int
    papers_summarized: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None


class BackfillJobsResponse(BaseModel):
    items: list[BackfillJobOut]
    page: int
    page_size: int
    total: int


def _accept_categories_alias(data: object) -> object:
    if not isinstance(data, dict):
        return data
    if "category_scope" in data or "categories" not in data:
        return data
    return {**data, "category_scope": data["categories"]}


class StatsOut(BaseModel):
    papers_total: int
    papers_summarized: int
    papers_saved: int
    feedback_total: int
    digest_runs_total: int
    llm_calls_total: int
    llm_tokens_total: int
    estimated_llm_cost_usd: float
    categories: dict[str, int]
