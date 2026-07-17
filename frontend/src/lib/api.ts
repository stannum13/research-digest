import type {
  ApiError,
  BackfillJob,
  BackfillJobRequest,
  BackfillJobsResponse,
  BackfillStatusName,
  ClassificationRun,
  ClassificationRunRequest,
  ClassificationStatus,
  DigestLatestResponse,
  DigestRun,
  DigestRunDetail,
  DigestRunRequest,
  DigestStatus,
  FeedbackOut,
  FeedbackSignal,
  PaperClassificationsResponse,
  PaperQueryParams,
  PapersResponse,
  PaperWithBreakdown,
  SearchCacheDeleteResponse,
  SearchCacheStatusResponse,
  SearchQueryParams,
  SearchResponse,
  Stats,
  SynthesisRun,
  SynthesisRunRequest,
  SynthesisRunsResponse,
} from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

class DigestApiError extends Error {
  detail?: string | null;
  status: number;

  constructor(status: number, payload: ApiError) {
    super(payload.error || "Digest API request failed");
    this.name = "DigestApiError";
    this.status = status;
    this.detail = payload.detail;
  }
}

function toSearchParams(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    search.set(key, String(value));
  });

  const query = search.toString();
  return query ? `?${query}` : "";
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let payload: ApiError = { error: response.statusText || "API error" };

    try {
      payload = (await response.json()) as ApiError;
    } catch {
      // Keep the status text fallback when the server returns a non-JSON error.
    }

    throw new DigestApiError(response.status, payload);
  }

  return (await response.json()) as T;
}

export function getPapers(params: PaperQueryParams = {}): Promise<PapersResponse> {
  return fetchJson<PapersResponse>(`/papers${toSearchParams(params)}`);
}

export function searchPapers(params: SearchQueryParams): Promise<SearchResponse> {
  return fetchJson<SearchResponse>(`/search${toSearchParams(params)}`);
}

export function getSearchCacheStatus(): Promise<SearchCacheStatusResponse> {
  return fetchJson<SearchCacheStatusResponse>("/search/cache/status");
}

export function clearSearchCache(): Promise<SearchCacheDeleteResponse> {
  return fetchJson<SearchCacheDeleteResponse>("/search/cache", {
    method: "DELETE",
  });
}

export function deleteSearchCacheEntry(cacheId: number): Promise<SearchCacheDeleteResponse> {
  return fetchJson<SearchCacheDeleteResponse>(`/search/cache/${encodeURIComponent(String(cacheId))}`, {
    method: "DELETE",
  });
}

export function getDigestStatus(): Promise<DigestStatus> {
  return fetchJson<DigestStatus>("/digest/status");
}

export function getLatestDigest(): Promise<DigestLatestResponse> {
  return fetchJson<DigestLatestResponse>("/digest/latest");
}

export function getDigestRunDetail(runId: number): Promise<DigestRunDetail> {
  return fetchJson<DigestRunDetail>(`/digest/runs/${encodeURIComponent(String(runId))}`);
}

export function createBackfillJob(payload: BackfillJobRequest): Promise<BackfillJob> {
  return fetchJson<BackfillJob>("/backfill/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBackfillJobs(params: { status?: BackfillStatusName; page?: number; page_size?: number } = {}): Promise<BackfillJobsResponse> {
  return fetchJson<BackfillJobsResponse>(`/backfill/jobs${toSearchParams(params)}`);
}

export function getBackfillJob(jobId: number): Promise<BackfillJob> {
  return fetchJson<BackfillJob>(`/backfill/jobs/${encodeURIComponent(String(jobId))}`);
}

export function runBackfillJob(jobId: number): Promise<BackfillJob> {
  return fetchJson<BackfillJob>(`/backfill/jobs/${encodeURIComponent(String(jobId))}/run`, {
    method: "POST",
  });
}

export function getStats(): Promise<Stats> {
  return fetchJson<Stats>("/stats");
}

export function togglePaperSave(arxivId: string): Promise<PaperWithBreakdown> {
  return fetchJson<PaperWithBreakdown>(`/papers/${encodeURIComponent(arxivId)}/save`, {
    method: "POST",
  });
}

export function getPaperClassifications(arxivId: string): Promise<PaperClassificationsResponse> {
  return fetchJson<PaperClassificationsResponse>(
    `/papers/${encodeURIComponent(arxivId)}/classifications`,
  );
}

export function classifyPaper(arxivId: string): Promise<PaperClassificationsResponse> {
  return fetchJson<PaperClassificationsResponse>(`/papers/${encodeURIComponent(arxivId)}/classify`, {
    method: "POST",
  });
}

export function getClassificationStatus(): Promise<ClassificationStatus> {
  return fetchJson<ClassificationStatus>("/classifications/status");
}

export function runClassifications(request: ClassificationRunRequest): Promise<ClassificationRun> {
  return fetchJson<ClassificationRun>(`/classifications/run${toSearchParams(request)}`, {
    method: "POST",
  });
}

export function sendPaperFeedback(
  arxivId: string,
  signal: FeedbackSignal,
  note?: string,
): Promise<FeedbackOut> {
  return fetchJson<FeedbackOut>(`/papers/${encodeURIComponent(arxivId)}/feedback`, {
    method: "POST",
    body: JSON.stringify({ signal, note }),
  });
}

export function runDigest(payload?: DigestRunRequest): Promise<DigestRun> {
  return fetchJson<DigestRun>("/digest/run", {
    method: "POST",
    body: payload ? JSON.stringify(payload) : undefined,
  }).then((job) =>
    fetchJson<DigestRun>(`/digest/runs/${encodeURIComponent(String(job.id))}/run`, {
      method: "POST",
    }),
  );
}

export function runDigestJob(runId: number): Promise<DigestRun> {
  return fetchJson<DigestRun>(`/digest/runs/${encodeURIComponent(String(runId))}/run`, {
    method: "POST",
  });
}

export function createSynthesisRun(payload: SynthesisRunRequest): Promise<SynthesisRun> {
  return fetchJson<SynthesisRun>("/synthesis/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSynthesisRuns(): Promise<SynthesisRunsResponse> {
  return fetchJson<SynthesisRunsResponse>("/synthesis/runs");
}

export function getSynthesisRun(runId: number): Promise<SynthesisRun> {
  return fetchJson<SynthesisRun>(`/synthesis/runs/${encodeURIComponent(String(runId))}`);
}
