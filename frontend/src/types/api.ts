export type NoveltyType =
  | "method"
  | "benchmark"
  | "dataset"
  | "theory"
  | "systems"
  | "empirical"
  | "application"
  | "survey"
  | "other";

export type Difficulty = "beginner" | "intermediate" | "expert";
export type Confidence = "low" | "medium" | "high";
export type DigestStatusName =
  | "idle"
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "partial"
  | "budget_exhausted";
export type BackfillStatusName =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "budget_exhausted"
  | "canceled";

export type FeedbackSignal =
  | "more_like_this"
  | "less_like_this"
  | "important"
  | "hide"
  | "read_later";

export type ApiError = {
  error: string;
  detail?: string | null;
};

export type GlossaryTerm = {
  term: string;
  definition: string;
};

export type PaperBreakdown = {
  one_line_takeaway: string;
  simple_summary: string;
  context: string;
  what_is_new: string;
  mechanism: string;
  evidence: string;
  methodology_caveats: string[];
  meaningful_extensions: string[];
  novelty_type: NoveltyType;
  difficulty: Difficulty;
  confidence: Confidence;
  read_this_if: string;
  tags: string[];
  vibe: string;
  glossary: GlossaryTerm[];
  follow_up_questions: string[];
  model_provider: string;
  model_name: string;
  source_basis: "abstract_only" | "partial_full_text" | "full_text";
  created_at: string;
};

export type PaperWithBreakdown = {
  id: number;
  arxiv_id: string;
  arxiv_version: string | null;
  title: string;
  abstract: string;
  authors: string[];
  primary_category: string;
  categories: string[];
  published_at: string;
  updated_at: string;
  arxiv_url: string;
  pdf_url: string;
  is_summarized: boolean;
  is_saved: boolean;
  score: number | null;
  breakdown: PaperBreakdown | null;
};

export type PaperClassification = {
  id: number;
  label_type: string;
  label: string;
  confidence: number | null;
  source: string;
  rationale: string | null;
  created_at: string;
};

export type PaperClassificationsResponse = {
  paper_id: number;
  arxiv_id: string;
  items: PaperClassification[];
};

export type ClassificationStatus = {
  label_type_counts: Record<string, number>;
  classified_paper_count: number;
  summarized_paper_count: number;
  coverage_percentage: number;
  total_labels: number;
};

export type ClassificationRunRequest = {
  limit?: number;
  only_missing: boolean;
};

export type ClassificationRun = {
  only_missing: boolean;
  limit: number | null;
  papers_processed: number;
  paper_ids: number[];
  arxiv_ids: string[];
  status: ClassificationStatus;
};

export type DigestStatus = {
  last_run_at: string | null;
  status: DigestStatusName;
  papers_summarized_today: number;
  error_message?: string | null;
};

export type PapersResponse = {
  items: PaperWithBreakdown[];
  page: number;
  page_size: number;
  total: number;
  digest_status: DigestStatus;
};

export type SearchQueryParams = {
  q?: string;
  label_type?: string;
  label?: string;
  limit?: number;
};

export type SearchResult = {
  paper: PaperWithBreakdown;
  score: number;
  matched_fields: string[];
  matched_labels: string[];
  reason: string;
};

export type SearchResponse = {
  items: SearchResult[];
  total: number;
  query: string;
};

export type SearchCacheEntry = {
  id: number;
  normalized_q: string;
  normalized_label_type: string;
  normalized_label: string;
  limit: number;
  cache_version: string;
  result_count: number;
  hit_count: number;
  created_at: string;
  updated_at: string;
  last_hit_at: string | null;
};

export type SearchCacheStatusResponse = {
  cache_version: string;
  total_entries: number;
  total_hits: number;
  entries: SearchCacheEntry[];
};

export type SearchCacheDeleteResponse = {
  cache_version: string;
  deleted_count: number;
};

export type DigestRun = {
  id: number;
  target_date: string | null;
  category_scope: string[];
  started_at: string;
  completed_at: string | null;
  status: string;
  papers_fetched: number;
  papers_new: number;
  papers_summarized: number;
  error_message: string | null;
  message?: string | null;
};

export type DigestRunRequest = {
  target_date?: string;
  category_scope?: string[];
};

export type LlmCall = {
  id: number;
  paper_id: number | null;
  arxiv_id: string | null;
  paper_title: string | null;
  task: string;
  provider: string;
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type DigestRunDetail = DigestRun & {
  config: Record<string, unknown>;
  llm_calls: LlmCall[];
  llm_tokens_total: number;
  estimated_llm_cost_usd: number;
};

export type BackfillJobRequest = {
  start_date: string;
  end_date: string;
  category_scope?: string[];
  budget_usd?: number;
};

export type BackfillJob = {
  id: number;
  start_date: string;
  end_date: string;
  category_scope: string[];
  status: BackfillStatusName;
  budget_usd: number;
  estimated_cost_usd: number;
  budget_remaining_usd: number;
  total_days: number;
  completed_days: number;
  failed_days: number;
  papers_fetched: number;
  papers_new: number;
  papers_summarized: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  message?: string | null;
};

export type BackfillJobsResponse = {
  items: BackfillJob[];
  page: number;
  page_size: number;
  total: number;
};

export type DigestLatestResponse = {
  run: DigestRun | null;
  papers: PaperWithBreakdown[];
};

export type SynthesisRunRequest = {
  paper_ids: number[];
  mode: SynthesisMode;
  instructions?: string;
};

export type SynthesisMode = "overview" | "compare" | "argument_map" | "research_plan";

export type SynthesisOutputValue =
  | null
  | string
  | number
  | boolean
  | string[]
  | number[]
  | Record<string, unknown>
  | Array<Record<string, unknown>>;

export type SynthesisOutput = {
  argument_map: SynthesisOutputValue;
  contradictions: SynthesisOutputValue;
  evidence_matrix: SynthesisOutputValue;
  open_questions: SynthesisOutputValue;
  extension_ideas: SynthesisOutputValue;
  replication_or_ablation_plan: SynthesisOutputValue;
  caveats: SynthesisOutputValue;
  source_paper_ids: number[];
  prompt_version: string;
  model_provider: string;
  model_name: string;
  created_at: string;
};

export type SynthesisRunSummary = {
  id: number;
  mode: SynthesisMode;
  instructions?: string | null;
  selected_paper_count: number;
  source_paper_ids: number[];
  prompt_version: string;
  model_provider: string;
  model_name: string;
  created_at: string;
};

export type SynthesisRun = SynthesisRunSummary &
  Omit<SynthesisOutput, "source_paper_ids" | "prompt_version" | "model_provider" | "model_name" | "created_at"> & {
    selected_papers: PaperWithBreakdown[];
  };

export type SynthesisRunsResponse = {
  items: SynthesisRunSummary[];
  page: number;
  page_size: number;
  total: number;
};

export type FeedbackOut = {
  id: number;
  paper_id: number;
  signal: FeedbackSignal;
  note: string | null;
  created_at: string;
};

export type Stats = {
  papers_total: number;
  papers_summarized: number;
  papers_saved: number;
  feedback_total: number;
  digest_runs_total: number;
  llm_calls_total: number;
  llm_tokens_total: number;
  estimated_llm_cost_usd: number;
  categories: Record<string, number>;
};

export type PaperQueryParams = {
  date?: string;
  category?: string;
  saved?: boolean;
  difficulty?: Difficulty;
  q?: string;
  page?: number;
  page_size?: number;
};
