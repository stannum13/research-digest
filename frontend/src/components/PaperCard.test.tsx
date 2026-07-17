import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSynthesisSelection } from "../context/SynthesisSelectionContext";
import type { SelectedSynthesisPaper } from "../context/SynthesisSelectionContext";
import { SYNTHESIS_SELECTION_STORAGE_KEY, SynthesisSelectionProvider } from "../context/SynthesisSelectionProvider";
import { mockPaper } from "../mocks/seedPapers";
import type { PaperClassification, PaperWithBreakdown } from "../types/api";
import { PaperCard } from "./PaperCard";

let fetchMock: ReturnType<typeof vi.fn>;

function renderWithQueryClient({
  initialSelected = [],
  paper = mockPaper,
}: {
  initialSelected?: SelectedSynthesisPaper[];
  paper?: PaperWithBreakdown;
} = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SynthesisSelectionProvider initialSelected={initialSelected}>
        <SelectionCountProbe />
        <PaperCard paper={paper} index={0} />
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

function classificationsResponse(items: PaperClassification[] = []) {
  return {
    paper_id: mockPaper.id,
    arxiv_id: mockPaper.arxiv_id,
    items,
  };
}

const classificationItems: PaperClassification[] = [
  {
    id: 11,
    label_type: "research_area",
    label: "agent evaluation",
    confidence: 0.92,
    source: "deterministic",
    rationale: "The paper evaluates long-horizon agents.",
    created_at: "2026-06-30T14:00:00Z",
  },
  {
    id: 12,
    label_type: "contribution",
    label: "control loop",
    confidence: 0.84,
    source: "deterministic",
    rationale: "The summary highlights planning and critique.",
    created_at: "2026-06-30T14:00:00Z",
  },
];

describe("PaperCard", () => {
  beforeEach(() => {
    window.localStorage.removeItem(SYNTHESIS_SELECTION_STORAGE_KEY);
    fetchMock = vi.fn(async (url, init) => {
      const path = String(url);

      if (path.includes(`/papers/${mockPaper.arxiv_id}/classify`) && init?.method === "POST") {
        return apiResponse(classificationsResponse(classificationItems));
      }

      if (path.includes(`/papers/${mockPaper.arxiv_id}/classifications`)) {
        return apiResponse(classificationsResponse());
      }

      return apiResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the collapsed paper and expands editorial sections", async () => {
    renderWithQueryClient();

    expect(screen.getByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();
    expect(screen.getByText(/A promising agent-control loop/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /expand/i }));

    expect(await screen.findByText("Context")).toBeInTheDocument();
    expect(screen.getByText(/Long-horizon agents often fail/)).toBeInTheDocument();
    expect(screen.getByText("Possible Extensions")).toBeInTheDocument();
  });

  it("shows pending summary affordances without enabling expansion", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <PaperCard paper={{ ...mockPaper, breakdown: null, is_summarized: false, score: null }} index={0} />
      </QueryClientProvider>,
    );

    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /pending/i })).toBeDisabled();
    expect(screen.getByRole("link", { name: /open paper on arxiv/i })).toHaveAttribute("href", mockPaper.arxiv_url);
  });

  it("toggles a paper in the synthesis selection", () => {
    renderWithQueryClient();

    expect(screen.getByTestId("selection-count")).toHaveTextContent("0");

    fireEvent.click(screen.getByRole("button", { name: /add paper to synthesis selection/i }));

    expect(screen.getByTestId("selection-count")).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: /remove paper from synthesis selection/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: /remove paper from synthesis selection/i }));

    expect(screen.getByTestId("selection-count")).toHaveTextContent("0");
  });

  it("persists synthesis selections in localStorage", () => {
    const { unmount } = renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: /add paper to synthesis selection/i }));

    expect(JSON.parse(window.localStorage.getItem(SYNTHESIS_SELECTION_STORAGE_KEY) ?? "[]")).toEqual([
      expect.objectContaining({
        arxiv_id: mockPaper.arxiv_id,
        id: mockPaper.id,
        title: mockPaper.title,
      }),
    ]);

    unmount();
    renderWithQueryClient();

    expect(screen.getByTestId("selection-count")).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: /remove paper from synthesis selection/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("disables new synthesis selections at the cap", () => {
    const cappedSelection = Array.from({ length: 8 }, (_, index) => selectedPaper(index + 10));
    const ninthPaper = { ...mockPaper, id: 99, arxiv_id: "2606.30099" };

    renderWithQueryClient({ initialSelected: cappedSelection, paper: ninthPaper });

    expect(screen.getByRole("button", { name: /selection limit reached \(8\)/i })).toBeDisabled();
  });

  it("fetches and renders grouped classification labels when expanded", async () => {
    fetchMock.mockImplementation(async (url) => {
      const path = String(url);

      if (path.includes(`/papers/${mockPaper.arxiv_id}/classifications`)) {
        return apiResponse(classificationsResponse(classificationItems));
      }

      return apiResponse({});
    });

    renderWithQueryClient();

    expect(screen.queryByText("Classifications")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /expand/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes(`/papers/${mockPaper.arxiv_id}/classifications`),
        ),
      ).toBe(true);
    });

    expect(await screen.findByText("Research Area")).toBeInTheDocument();
    expect(screen.getByText("agent evaluation")).toBeInTheDocument();
    expect(screen.getByText("Contribution")).toBeInTheDocument();
    expect(screen.getByText("control loop")).toBeInTheDocument();
  });

  it("triggers classification when no labels are loaded", async () => {
    renderWithQueryClient();

    fireEvent.click(screen.getByRole("button", { name: /expand/i }));

    expect(await screen.findByText("No labels yet.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /extract labels/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).includes(`/papers/${mockPaper.arxiv_id}/classify`) &&
            init?.method === "POST",
        ),
      ).toBe(true);
    });

    expect(await screen.findByText("agent evaluation")).toBeInTheDocument();
    expect(screen.queryByText("No labels yet.")).not.toBeInTheDocument();
  });

});

function SelectionCountProbe() {
  const { selectedCount } = useSynthesisSelection();
  return <div data-testid="selection-count">{selectedCount}</div>;
}

function selectedPaper(id: number): SelectedSynthesisPaper {
  return {
    ...mockPaper,
    id,
    arxiv_id: `2606.30${String(id).padStart(3, "0")}`,
    title: `Selected paper ${id}`,
  };
}
