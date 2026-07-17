import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSearch } from "../hooks/useDigestApi";
import { mockPaper } from "../mocks/seedPapers";
import { StatusPage } from "./StatusPage";

const run = {
  id: 42,
  target_date: "2026-06-30",
  category_scope: ["cs.AI"],
  started_at: "2026-06-30T13:00:00Z",
  completed_at: "2026-06-30T13:03:00Z",
  status: "success",
  papers_fetched: 4,
  papers_new: 2,
  papers_summarized: 3,
  error_message: null,
  message: "Digest run completed.",
};

const stats = {
  papers_total: 8,
  papers_summarized: 6,
  papers_saved: 2,
  feedback_total: 1,
  digest_runs_total: 4,
  llm_calls_total: 3,
  llm_tokens_total: 1200,
  estimated_llm_cost_usd: 0.018,
  categories: { "cs.AI": 4 },
};

const classificationStatus = {
  label_type_counts: {
    method_family: 8,
    evidence_type: 4,
    caveat_class: 2,
    task: 3,
    dataset_or_benchmark: 1,
    architecture_primitive: 0,
    probe_family: 0,
  },
  classified_paper_count: 6,
  summarized_paper_count: 8,
  coverage_percentage: 75,
  total_labels: 18,
};

const completeClassificationStatus = {
  ...classificationStatus,
  label_type_counts: {
    ...classificationStatus.label_type_counts,
    method_family: 10,
    evidence_type: 6,
  },
  classified_paper_count: 8,
  coverage_percentage: 100,
  total_labels: 22,
};

const searchCacheStatus = {
  cache_version: "retrieval-search-v1",
  total_entries: 2,
  total_hits: 3,
  entries: [
    {
      id: 11,
      normalized_q: "agent evaluation",
      normalized_label_type: "method_family",
      normalized_label: "retrieval",
      limit: 25,
      cache_version: "retrieval-search-v1",
      result_count: 8,
      hit_count: 3,
      created_at: "2026-06-30T12:00:00Z",
      updated_at: "2026-06-30T12:05:00Z",
      last_hit_at: "2026-06-30T12:05:00Z",
    },
    {
      id: 12,
      normalized_q: "",
      normalized_label_type: "",
      normalized_label: "",
      limit: 10,
      cache_version: "retrieval-search-v1",
      result_count: 0,
      hit_count: 0,
      created_at: "2026-06-30T12:02:00Z",
      updated_at: "2026-06-30T12:02:00Z",
      last_hit_at: null,
    },
  ],
};

const backfillJob = {
  id: 101,
  start_date: "2026-06-29",
  end_date: "2026-06-30",
  category_scope: ["cs.AI"],
  status: "pending",
  budget_usd: 1,
  estimated_cost_usd: 0,
  budget_remaining_usd: 1,
  total_days: 2,
  completed_days: 0,
  failed_days: 0,
  papers_fetched: 0,
  papers_new: 0,
  papers_summarized: 0,
  error_message: null,
  created_at: "2026-06-30T13:00:00Z",
  started_at: null,
  completed_at: null,
  message: "Backfill job queued.",
};

let fetchMock: ReturnType<typeof vi.fn>;

function SearchProbe() {
  const search = useSearch({ q: "agent" });

  return <span data-testid="search-probe">{search.data?.total ?? "loading"}</span>;
}

function renderStatus({ withSearchProbe = false }: { withSearchProbe?: boolean } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <StatusPage />
      {withSearchProbe ? <SearchProbe /> : null}
    </QueryClientProvider>,
  );
}

function apiResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  };
}

function apiErrorResponse(status: number, payload: unknown) {
  return {
    ok: false,
    status,
    statusText: "API error",
    json: async () => payload,
  };
}

function countFetches(pathname: string) {
  return fetchMock.mock.calls.filter(([url]) => new URL(String(url)).pathname === pathname).length;
}

function hasFetch(pathname: string, method?: string) {
  return fetchMock.mock.calls.some(([url, init]) => {
    const requestedUrl = new URL(String(url));
    return requestedUrl.pathname === pathname && (!method || init?.method === method);
  });
}

describe("StatusPage", () => {
  beforeEach(() => {
    let currentClassificationStatus = classificationStatus;
    let currentSearchCacheStatus = searchCacheStatus;
    let searchRequestCount = 0;

    fetchMock = vi.fn(async (url, init) => {
      const path = String(url);
      const requestUrl = new URL(path);

      if (requestUrl.pathname === "/search/cache/status") {
        return apiResponse(currentSearchCacheStatus);
      }

      if (requestUrl.pathname === "/search/cache" && init?.method === "DELETE") {
        const deletedCount = currentSearchCacheStatus.total_entries;
        currentSearchCacheStatus = {
          ...currentSearchCacheStatus,
          total_entries: 0,
          total_hits: 0,
          entries: [],
        };
        return apiResponse({
          cache_version: currentSearchCacheStatus.cache_version,
          deleted_count: deletedCount,
        });
      }

      if (requestUrl.pathname.startsWith("/search/cache/") && init?.method === "DELETE") {
        const cacheId = Number(requestUrl.pathname.split("/").pop());
        const remainingEntries = currentSearchCacheStatus.entries.filter((entry) => entry.id !== cacheId);

        if (remainingEntries.length === currentSearchCacheStatus.entries.length) {
          return apiErrorResponse(404, { error: "Search cache entry not found" });
        }

        currentSearchCacheStatus = {
          ...currentSearchCacheStatus,
          total_entries: remainingEntries.length,
          total_hits: remainingEntries.reduce((sum, entry) => sum + entry.hit_count, 0),
          entries: remainingEntries,
        };
        return apiResponse({
          cache_version: currentSearchCacheStatus.cache_version,
          deleted_count: 1,
        });
      }

      if (requestUrl.pathname === "/search") {
        searchRequestCount += 1;
        return apiResponse({
          items: [],
          total: searchRequestCount,
          query: requestUrl.searchParams.get("q") ?? "",
        });
      }

      if (path.includes("/digest/status")) {
        return apiResponse({
          last_run_at: run.completed_at,
          status: "success",
          papers_summarized_today: 3,
          error_message: null,
        });
      }

      if (path.includes("/digest/latest")) {
        return apiResponse({ run, papers: [mockPaper] });
      }

      if (path.includes("/digest/runs/42")) {
        return apiResponse({
          ...run,
          config: { target_date: run.target_date, categories: run.category_scope },
          llm_calls: [
            {
              id: 7,
              paper_id: 1,
              arxiv_id: mockPaper.arxiv_id,
              paper_title: mockPaper.title,
              task: "summary",
              provider: "zai",
              model_name: "glm-4.5",
              prompt_tokens: 800,
              completion_tokens: 434,
              total_tokens: 1234,
              estimated_cost_usd: 0.0123,
              metadata: {},
              created_at: "2026-06-30T13:02:00Z",
            },
          ],
          llm_tokens_total: 1234,
          estimated_llm_cost_usd: 0.0123,
        });
      }

      if (path.includes("/stats")) {
        return apiResponse(stats);
      }

      if (path.includes("/classifications/status")) {
        return apiResponse(currentClassificationStatus);
      }

      if (path.includes("/classifications/run") && init?.method === "POST") {
        currentClassificationStatus = completeClassificationStatus;
        return apiResponse({
          only_missing: true,
          limit: 25,
          papers_processed: 2,
          paper_ids: [2, 3],
          arxiv_ids: ["2606.30002", "2606.30003"],
          status: completeClassificationStatus,
        });
      }

      if (path.includes("/backfill/jobs/101/run")) {
        return apiResponse({
          ...backfillJob,
          status: "success",
          budget_remaining_usd: 0.42,
          estimated_cost_usd: 0.58,
          completed_days: 2,
          papers_fetched: 7,
          papers_new: 6,
          papers_summarized: 5,
          started_at: "2026-06-30T13:01:00Z",
          completed_at: "2026-06-30T13:06:00Z",
        });
      }

      if (path.includes("/backfill/jobs")) {
        return apiResponse({
          items: [backfillJob],
          page: 1,
          page_size: 20,
          total: 1,
        });
      }

      return apiResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads accounting for the latest run detail", async () => {
    renderStatus();

    expect(await screen.findByText("Run #42")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/digest/runs/42"))).toBe(true);
    });

    expect(await screen.findByText("$0.0123")).toBeInTheDocument();
    expect(screen.getByText("1234")).toBeInTheDocument();
    expect(screen.getByText("2026-06-30")).toBeInTheDocument();
    expect(await screen.findByText("1 tracked")).toBeInTheDocument();
    expect(screen.getByText(/job #101/i)).toBeInTheDocument();
    expect(screen.getByText("0/2 days · 0 failed · 0/0 summarized")).toBeInTheDocument();
    expect(screen.getByText("$1.00 of $1.00 remaining · $0.00 estimated")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run backfill job #101/i })).toBeEnabled();
  });

  it("renders search cache status and recent entries", async () => {
    renderStatus();

    const section = (await screen.findByText("Search Cache")).closest("section") as HTMLElement;
    const cache = within(section);

    expect(await cache.findByText("retrieval-search-v1")).toBeInTheDocument();
    expect(cache.getByText("Total entries")).toBeInTheDocument();
    expect(cache.getByText("Total hits")).toBeInTheDocument();
    expect(cache.getByText("agent evaluation")).toBeInTheDocument();
    expect(cache.getByText("Method family / retrieval")).toBeInTheDocument();
    expect(cache.getByText("Any query")).toBeInTheDocument();
    expect(cache.getByText("All labels")).toBeInTheDocument();
    expect(cache.getByRole("button", { name: /clear all search cache entries/i })).toBeEnabled();
    expect(cache.getByRole("button", { name: /delete search cache entry 11/i })).toBeEnabled();
  });

  it("clears all search cache entries and refreshes status", async () => {
    renderStatus();

    const section = (await screen.findByText("Search Cache")).closest("section") as HTMLElement;
    const cache = within(section);
    const clearButton = await cache.findByRole("button", { name: /clear all search cache entries/i });

    await waitFor(() => {
      expect(clearButton).toBeEnabled();
    });
    fireEvent.click(clearButton);

    expect(await cache.findByText("Cleared 2 cache entries.")).toBeInTheDocument();
    expect(await cache.findByText("No search cache entries yet.")).toBeInTheDocument();
    expect(hasFetch("/search/cache", "DELETE")).toBe(true);

    await waitFor(() => {
      expect(countFetches("/search/cache/status")).toBeGreaterThanOrEqual(2);
    });
  });

  it("deletes a targeted search cache entry and refreshes status", async () => {
    renderStatus();

    const section = (await screen.findByText("Search Cache")).closest("section") as HTMLElement;
    const cache = within(section);
    const deleteButton = await cache.findByRole("button", { name: /delete search cache entry 11/i });

    await waitFor(() => {
      expect(deleteButton).toBeEnabled();
    });
    fireEvent.click(deleteButton);

    expect(await cache.findByText("Deleted 1 cache entry.")).toBeInTheDocument();
    await waitFor(() => {
      expect(cache.queryByText("agent evaluation")).not.toBeInTheDocument();
    });
    expect(cache.getByText("Any query")).toBeInTheDocument();
    expect(hasFetch("/search/cache/11", "DELETE")).toBe(true);
  });

  it("invalidates active search queries after cache maintenance", async () => {
    renderStatus({ withSearchProbe: true });

    await waitFor(() => {
      expect(countFetches("/search")).toBe(1);
    });

    const section = (await screen.findByText("Search Cache")).closest("section") as HTMLElement;
    const clearButton = await within(section).findByRole("button", {
      name: /clear all search cache entries/i,
    });

    await waitFor(() => {
      expect(clearButton).toBeEnabled();
    });
    fireEvent.click(clearButton);

    await waitFor(() => {
      expect(countFetches("/search")).toBeGreaterThan(1);
    });
  });

  it("renders classification coverage status and label counts", async () => {
    renderStatus();

    const section = (await screen.findByText("Ontology Coverage")).closest("section");
    expect(section).not.toBeNull();

    const coverageSection = within(section as HTMLElement);
    expect(await coverageSection.findByText("2 missing classifications")).toBeInTheDocument();
    expect(coverageSection.getAllByText("75%").length).toBeGreaterThan(0);
    expect(coverageSection.getByText("Summarized papers")).toBeInTheDocument();
    expect(coverageSection.getByText("Classified papers")).toBeInTheDocument();
    expect(coverageSection.getByText("Total labels")).toBeInTheDocument();
    expect(coverageSection.getByText("Method family")).toBeInTheDocument();
    expect(coverageSection.getByText("Dataset or benchmark")).toBeInTheDocument();
    expect(coverageSection.getByRole("button", { name: /run missing classifications/i })).toBeEnabled();
  });

  it("runs a missing-classification batch and refreshes coverage", async () => {
    renderStatus();

    const section = (await screen.findByText("Ontology Coverage")).closest("section") as HTMLElement;
    expect(await within(section).findByText("2 missing classifications")).toBeInTheDocument();

    fireEvent.change(within(section).getByLabelText(/classification batch limit/i), {
      target: { value: "2" },
    });
    const runButton = within(section).getByRole("button", { name: /run missing classifications/i });
    fireEvent.submit(runButton.closest("form") as HTMLFormElement);

    expect(await within(section).findByText(/Last batch: 2 papers processed/)).toBeInTheDocument();
    expect(within(section).getAllByText("100%").length).toBeGreaterThan(0);

    const runCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("/classifications/run") && init?.method === "POST",
    );
    expect(runCall).toBeTruthy();

    const requestedUrl = new URL(String(runCall?.[0]));
    expect(requestedUrl.searchParams.get("limit")).toBe("2");
    expect(requestedUrl.searchParams.get("only_missing")).toBe("true");
  });

  it("disables missing runs when coverage is complete and shows run errors", async () => {
    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url);

      if (path.includes("/digest/status")) {
        return apiResponse({
          last_run_at: run.completed_at,
          status: "success",
          papers_summarized_today: 3,
          error_message: null,
        });
      }

      if (path.includes("/digest/latest")) {
        return apiResponse({ run, papers: [mockPaper] });
      }

      if (path.includes("/digest/runs/42")) {
        return apiResponse({
          ...run,
          config: { target_date: run.target_date, categories: run.category_scope },
          llm_calls: [],
          llm_tokens_total: 0,
          estimated_llm_cost_usd: 0,
        });
      }

      if (path.includes("/stats")) {
        return apiResponse(stats);
      }

      if (path.includes("/classifications/status")) {
        return apiResponse(completeClassificationStatus);
      }

      if (path.includes("/classifications/run") && init?.method === "POST") {
        return apiErrorResponse(503, { error: "Classification provider unavailable." });
      }

      if (path.includes("/backfill/jobs")) {
        return apiResponse({
          items: [backfillJob],
          page: 1,
          page_size: 20,
          total: 1,
        });
      }

      return apiResponse({});
    });

    renderStatus();

    const section = (await screen.findByText("Ontology Coverage")).closest("section") as HTMLElement;
    expect(await within(section).findByText("0 missing classifications")).toBeInTheDocument();

    const missingButton = within(section).getByRole("button", { name: /run missing classifications/i });
    expect(missingButton).toBeDisabled();

    fireEvent.click(within(section).getByLabelText(/only missing classifications/i));
    const rerunButton = within(section).getByRole("button", {
      name: /run classifications for all summarized papers/i,
    });
    expect(rerunButton).toBeEnabled();
    fireEvent.submit(rerunButton.closest("form") as HTMLFormElement);

    expect(await within(section).findByText(/Classification run failed: Classification provider unavailable./i)).toBeInTheDocument();
  });

  it("shows a clear error when the backfill run endpoint fails", async () => {
    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url);

      if (path.includes("/digest/status")) {
        return apiResponse({
          last_run_at: run.completed_at,
          status: "success",
          papers_summarized_today: 3,
          error_message: null,
        });
      }

      if (path.includes("/digest/latest")) {
        return apiResponse({ run, papers: [mockPaper] });
      }

      if (path.includes("/digest/runs/42")) {
        return apiResponse({
          ...run,
          config: { target_date: run.target_date, categories: run.category_scope },
          llm_calls: [],
          llm_tokens_total: 0,
          estimated_llm_cost_usd: 0,
        });
      }

      if (path.includes("/stats")) {
        return apiResponse(stats);
      }

      if (path.includes("/classifications/status")) {
        return apiResponse(classificationStatus);
      }

      if (path.includes("/backfill/jobs/101/run") && init?.method === "POST") {
        return apiErrorResponse(409, { error: "Job is not runnable.", detail: "Only pending jobs can run." });
      }

      if (path.includes("/backfill/jobs")) {
        return apiResponse({
          items: [backfillJob],
          page: 1,
          page_size: 20,
          total: 1,
        });
      }

      return apiResponse({});
    });

    renderStatus();

    expect(await screen.findByText(/job #101/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /run backfill job #101/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Run failed: Job is not runnable.");
  });
});
