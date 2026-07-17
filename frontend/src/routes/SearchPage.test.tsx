import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mockPaper } from "../mocks/seedPapers";
import { SearchPage } from "./SearchPage";

let fetchMock: ReturnType<typeof vi.fn>;

function renderSearch(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/search" element={<SearchPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function apiResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  };
}

function searchResponse() {
  return {
    items: [
      {
        paper: mockPaper,
        score: 0.873,
        matched_fields: ["title", "abstract"],
        matched_labels: ["method: retrieval", "task: agents"],
        reason: "Title and ontology labels matched retrieval.",
      },
    ],
    total: 1,
    query: "agent evaluation",
  };
}

describe("SearchPage", () => {
  beforeEach(() => {
    fetchMock = vi.fn(async () => apiResponse(searchResponse()));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests search results with query and label filters from the URL", async () => {
    renderSearch("/search?q=agent%20evaluation&label_type=method_family&label=retrieval");

    expect(await screen.findByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();

    const requestedUrl = new URL(String(fetchMock.mock.calls[0][0]));
    expect(requestedUrl.pathname).toBe("/search");
    expect(requestedUrl.searchParams.get("q")).toBe("agent evaluation");
    expect(requestedUrl.searchParams.get("label_type")).toBe("method_family");
    expect(requestedUrl.searchParams.get("label")).toBe("retrieval");
    expect(screen.getByLabelText("Search query")).toHaveValue("agent evaluation");
    expect(screen.getByLabelText("Label type")).toHaveValue("method_family");
    expect(screen.getByLabelText("Label")).toHaveValue("retrieval");
  });

  it("submits form filters as search query params", async () => {
    renderSearch("/search");

    expect(screen.getByText("No query submitted.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "long horizon" } });
    fireEvent.change(screen.getByLabelText("Label type"), { target: { value: "task" } });
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "agents" } });
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const requestedUrl = new URL(String(fetchMock.mock.calls[0][0]));
    expect(requestedUrl.pathname).toBe("/search");
    expect(requestedUrl.searchParams.get("q")).toBe("long horizon");
    expect(requestedUrl.searchParams.get("label_type")).toBe("task");
    expect(requestedUrl.searchParams.get("label")).toBe("agents");
  });

  it("renders score, reason, matched fields, matched labels, category, and arXiv link", async () => {
    renderSearch("/search?q=agent");

    expect(await screen.findByText("Quiet Tools for Long-Horizon Language Agents")).toBeInTheDocument();
    expect(screen.getByText("cs.AI")).toBeInTheDocument();
    expect(screen.getByText("Score 0.87")).toBeInTheDocument();
    expect(screen.getByText("Title and ontology labels matched retrieval.")).toBeInTheDocument();
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText("abstract")).toBeInTheDocument();
    expect(screen.getByText("method: retrieval")).toBeInTheDocument();
    expect(screen.getByText("task: agents")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open arxiv/i })).toHaveAttribute("href", mockPaper.arxiv_url);
  });
});
