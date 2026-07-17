import { createContext, useContext } from "react";

import type { PaperWithBreakdown } from "../types/api";

export const MAX_SYNTHESIS_SELECTION = 8;

export type SelectedSynthesisPaper = Pick<
  PaperWithBreakdown,
  | "id"
  | "arxiv_id"
  | "title"
  | "authors"
  | "primary_category"
  | "categories"
  | "published_at"
  | "updated_at"
  | "score"
  | "breakdown"
>;

export type SynthesisSelectionContextValue = {
  selectedPapers: SelectedSynthesisPaper[];
  selectedIds: number[];
  selectedCount: number;
  limit: number;
  isSelected: (paperId: number) => boolean;
  canSelectPaper: (paperId: number) => boolean;
  togglePaper: (paper: PaperWithBreakdown) => void;
  removePaper: (paperId: number) => void;
  clearSelection: () => void;
};

const fallbackContext: SynthesisSelectionContextValue = {
  selectedPapers: [],
  selectedIds: [],
  selectedCount: 0,
  limit: MAX_SYNTHESIS_SELECTION,
  isSelected: () => false,
  canSelectPaper: () => true,
  togglePaper: () => {},
  removePaper: () => {},
  clearSelection: () => {},
};

export const SynthesisSelectionContext = createContext<SynthesisSelectionContextValue>(fallbackContext);

export function useSynthesisSelection() {
  return useContext(SynthesisSelectionContext);
}

export function toSelectedSynthesisPaper(paper: PaperWithBreakdown): SelectedSynthesisPaper {
  return {
    id: paper.id,
    arxiv_id: paper.arxiv_id,
    title: paper.title,
    authors: paper.authors,
    primary_category: paper.primary_category,
    categories: paper.categories,
    published_at: paper.published_at,
    updated_at: paper.updated_at,
    score: paper.score,
    breakdown: paper.breakdown,
  };
}
