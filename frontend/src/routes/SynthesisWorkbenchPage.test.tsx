import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SYNTHESIS_SELECTION_STORAGE_KEY, SynthesisSelectionProvider } from "../context/SynthesisSelectionProvider";
import { mockPaper } from "../mocks/seedPapers";
import type { PaperWithBreakdown, SynthesisRun, SynthesisRunSummary } from "../types/api";
import { SynthesisWorkbenchPage } from "./SynthesisWorkbenchPage";

let fetchMock: ReturnType<typeof vi.fn>;

const secondPaper: PaperWithBreakdown = {
  ...mockPaper,
  id: 2,
  arxiv_id: "2606.30002",
  title: "Evaluation Benchmarks for Agent Audits",
  authors: ["Ira Nelson", "Sam Ortiz"],
  primary_category: "cs.LG",
  categories: ["cs.LG", "stat.ML"],
};

function renderWorkbench({ initialSelected = [mockPaper, secondPaper] }: { initialSelected?: PaperWithBreakdown[] } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SynthesisSelectionProvider initialSelected={initialSelected}>
        <MemoryRouter>
          <SynthesisWorkbenchPage />
        </MemoryRouter>
      </SynthesisSelectionProvider>
    </QueryClientProvider>,
  );
}

function apiResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  };
}

function synthesisRun(): SynthesisRun {
  return {
    id: 42,
    mode: "compare",
    instructions: "Focus on evaluation gaps.",
    selected_paper_count: 2,
    source_paper_ids: [1, 2],
    prompt_version: "synthesis-workbench-deterministic-v1",
    model_provider: "none",
    model_name: "metadata-breakdown-heuristic-v1",
    created_at: "2026-06-30T14:00:00Z",
    selected_papers: [mockPaper, secondPaper],
    argument_map: [{ claim: "Shared claim: structured review loops reduce drift." }],
    contradictions: [
      {
        note: "One paper reports gains on simulated tasks while the benchmark paper shows weaker live-task gains.",
      },
    ],
    evidence_matrix: [
      {
        claim: "Audit loop helps",
        source: "2606.30001",
        evidence: "Ablation win rate improves after critique.",
      },
    ],
    open_questions: [{ question: "Does the loop hold under live coding pressure?" }],
    extension_ideas: [{ idea: "Measure evaluator sensitivity across benchmark families." }],
    replication_or_ablation_plan: [{ action: "Remove critic and compare failure recovery." }],
    caveats: [{ caveat: "Seeded output for frontend tests." }],
  };
}

function runSummary(run: SynthesisRun): SynthesisRunSummary {
  return {
    id: run.id,
    mode: run.mode,
    instructions: run.instructions,
    selected_paper_count: run.selected_paper_count,
    source_paper_ids: run.source_paper_ids,
    prompt_version: run.prompt_version,
    model_provider: run.model_provider,
    model_name: run.model_name,
    created_at: run.created_at,
  };
}

describe("SynthesisWorkbenchPage", () => {
  beforeEach(() => {
    window.localStorage.removeItem(SYNTHESIS_SELECTION_STORAGE_KEY);
    fetchMock = vi.fn(async (url, init) => {
      const path = String(url);

      if (path.endsWith("/synthesis/runs") && init?.method === "POST") {
        return apiResponse(synthesisRun());
      }

      if (path.endsWith("/synthesis/runs/42")) {
        return apiResponse(synthesisRun());
      }

      if (path.endsWith("/synthesis/runs")) {
        return apiResponse({
          items: [],
          page: 1,
          page_size: 20,
          total: 0,
        });
      }

      return apiResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    window.localStorage.removeItem(SYNTHESIS_SELECTION_STORAGE_KEY);
    vi.unstubAllGlobals();
  });

  it("posts selected paper ids and renders structured synthesis output", async () => {
    renderWorkbench();

    expect(screen.getByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();
    expect(screen.getByText("Evaluation Benchmarks for Agent Audits")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/synthesis instructions/i), {
      target: { value: "Focus on evaluation gaps." },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate synthesis/i }));

    await waitFor(() => {
      const postCalls = fetchMock.mock.calls.filter(
        ([url, init]) => String(url).endsWith("/synthesis/runs") && init?.method === "POST",
      );
      expect(postCalls).toHaveLength(1);
    });

    const [, postInit] = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/synthesis/runs") && init?.method === "POST",
    )!;

    expect(JSON.parse(String(postInit?.body))).toEqual({
      paper_ids: [1, 2],
      mode: "compare",
      instructions: "Focus on evaluation gaps.",
    });

    expect(await screen.findByText("Argument Map")).toBeInTheDocument();
    expect(screen.getByText(/Shared claim: structured review loops reduce drift/)).toBeInTheDocument();
    expect(screen.getByText("Contradictions")).toBeInTheDocument();
    expect(screen.getByText("Evidence Matrix")).toBeInTheDocument();
    expect(screen.getByText("Claim")).toBeInTheDocument();
    expect(screen.getByText(/Remove critic and compare failure recovery/)).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getAllByText(/Evaluation Benchmarks for Agent Audits/).length).toBeGreaterThan(0);
  });

  it("renders recent-run sources from fetched run detail selected_papers", async () => {
    const detailOnlyPaper: PaperWithBreakdown = {
      ...mockPaper,
      id: 77,
      arxiv_id: "2606.30077",
      title: "Detail Sources for Archived Synthesis Runs",
      authors: ["Noor Patel"],
      primary_category: "cs.CL",
      categories: ["cs.CL"],
    };
    const detailRun: SynthesisRun = {
      ...synthesisRun(),
      id: 77,
      mode: "overview",
      selected_paper_count: 1,
      source_paper_ids: [detailOnlyPaper.id],
      selected_papers: [detailOnlyPaper],
      argument_map: [{ claim: "Recent run detail carries its own source metadata." }],
    };

    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url);

      if (path.endsWith("/synthesis/runs") && init?.method === "POST") {
        return apiResponse(synthesisRun());
      }

      if (path.endsWith("/synthesis/runs/77")) {
        return apiResponse(detailRun);
      }

      if (path.endsWith("/synthesis/runs")) {
        return apiResponse({
          items: [runSummary(detailRun)],
          page: 1,
          page_size: 20,
          total: 1,
        });
      }

      return apiResponse({});
    });

    renderWorkbench({ initialSelected: [mockPaper, secondPaper] });

    fireEvent.click(await screen.findByRole("button", { name: /run #77/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/synthesis/runs/77")),
      ).toBe(true);
    });

    expect(await screen.findByText("Detail Sources for Archived Synthesis Runs")).toBeInTheDocument();
    expect(screen.getByText(/2606\.30077/)).toBeInTheDocument();
  });
});
