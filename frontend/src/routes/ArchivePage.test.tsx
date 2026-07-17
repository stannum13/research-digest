import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mockPaper } from "../mocks/seedPapers";
import { ArchivePage } from "./ArchivePage";

const digestStatus = {
  last_run_at: "2026-06-30T13:10:00Z",
  status: "success",
  papers_summarized_today: 1,
  error_message: null,
};

let fetchMock: ReturnType<typeof vi.fn>;

function renderArchive(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/archive" element={<ArchivePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockPapersResponse() {
  fetchMock.mockImplementation(async (url) => {
    const path = String(url);

    if (path.includes("/backfill/jobs")) {
      return apiResponse({
        items: [],
        page: 1,
        page_size: 20,
        total: 0,
      });
    }

    return apiResponse(papersResponse());
  });
}

function apiResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  };
}

function papersResponse() {
  return {
    items: [mockPaper],
    page: 1,
    page_size: 10,
    total: 1,
    digest_status: digestStatus,
  };
}

function backfillJob(overrides: Record<string, unknown> = {}) {
  const job = {
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

  return { ...job, ...overrides };
}

describe("ArchivePage", () => {
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    mockPapersResponse();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests the selected archive date and category", async () => {
    renderArchive("/archive?date=2026-06-30&category=cs.AI");

    expect(await screen.findByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();
    expect(screen.getByText("Tuesday, June 30, 2026")).toBeInTheDocument();
    expect(screen.getByLabelText("Archive date")).toHaveValue("2026-06-30");
    expect(screen.getByRole("button", { name: /run selected archive date/i })).toBeEnabled();

    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/papers?");
    expect(String(url)).toContain("date=2026-06-30");
    expect(String(url)).toContain("category=cs.AI");
  });

  it("moves to the previous day from the date controls", async () => {
    renderArchive("/archive?date=2026-06-30");

    expect(await screen.findByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /previous day/i }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("date=2026-06-29"))).toBe(true);
    });
    expect(screen.getByLabelText("Archive date")).toHaveValue("2026-06-29");
  });

  it("requests a category-scoped backfill range", async () => {
    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url);

      if (path.includes("/backfill/jobs") && init?.method === "POST") {
        return apiResponse(backfillJob());
      }

      if (path.includes("/backfill/jobs")) {
        return apiResponse({
          items: [],
          page: 1,
          page_size: 20,
          total: 0,
        });
      }

      return apiResponse(papersResponse());
    });

    renderArchive("/archive?date=2026-06-30&category=cs.AI");

    expect(await screen.findByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Backfill from"), { target: { value: "2026-06-29" } });
    fireEvent.change(screen.getByLabelText("Backfill to"), { target: { value: "2026-06-30" } });
    fireEvent.click(screen.getByRole("button", { name: /start backfill/i }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/backfill/jobs")).length).toBeGreaterThanOrEqual(2);
    });

    const jobBodies = fetchMock.mock.calls
      .filter(([url, init]) => String(url).includes("/backfill/jobs") && init?.method === "POST")
      .map(([, init]) => JSON.parse(String(init?.body)));

    expect(jobBodies).toEqual([
      { start_date: "2026-06-29", end_date: "2026-06-30", category_scope: ["cs.AI"] },
    ]);
    expect(await screen.findByText(/job #101 queued for 2 days/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-06-29 to 2026-06-30/i)).toBeInTheDocument();
  });

  it("runs a queued backfill job and renders returned progress", async () => {
    let currentJob = backfillJob();

    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url);

      if (path.includes("/backfill/jobs/101/run") && init?.method === "POST") {
        currentJob = backfillJob({
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

        return apiResponse(currentJob);
      }

      if (path.includes("/backfill/jobs")) {
        return apiResponse({
          items: [currentJob],
          page: 1,
          page_size: 20,
          total: 1,
        });
      }

      return apiResponse(papersResponse());
    });

    renderArchive("/archive?date=2026-06-30&category=cs.AI");

    expect(await screen.findByText(/job #101/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /run backfill job #101/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) => String(url).includes("/backfill/jobs/101/run") && init?.method === "POST",
        ),
      ).toBe(true);
    });

    expect(await screen.findByText("2/2 days · 0 failed · 5/7 summarized")).toBeInTheDocument();
    expect(screen.getByText("$0.42 of $1.00 remaining · $0.58 estimated")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run backfill job #101/i })).not.toBeInTheDocument();
  });
});
