import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  MAX_SYNTHESIS_SELECTION,
  SynthesisSelectionContext,
  toSelectedSynthesisPaper,
} from "./SynthesisSelectionContext";
import type { SelectedSynthesisPaper, SynthesisSelectionContextValue } from "./SynthesisSelectionContext";
import type { PaperWithBreakdown } from "../types/api";

export const SYNTHESIS_SELECTION_STORAGE_KEY = "marginalia:synthesis-selection";

type SynthesisSelectionProviderProps = {
  children: ReactNode;
  initialSelected?: SelectedSynthesisPaper[];
};

export function SynthesisSelectionProvider({
  children,
  initialSelected = [],
}: SynthesisSelectionProviderProps) {
  const [selectedPapers, setSelectedPapers] = useState<SelectedSynthesisPaper[]>(() => {
    const initialSelection = normalizeSelectedPapers(initialSelected);

    return initialSelection.length > 0 ? initialSelection : readStoredSelection();
  });

  useEffect(() => {
    persistSelection(selectedPapers);
  }, [selectedPapers]);

  const selectedIds = useMemo(() => selectedPapers.map((paper) => paper.id), [selectedPapers]);
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const isSelected = useCallback((paperId: number) => selectedIdSet.has(paperId), [selectedIdSet]);

  const canSelectPaper = useCallback(
    (paperId: number) => selectedIdSet.has(paperId) || selectedPapers.length < MAX_SYNTHESIS_SELECTION,
    [selectedIdSet, selectedPapers.length],
  );

  const togglePaper = useCallback((paper: PaperWithBreakdown) => {
    setSelectedPapers((current) => {
      if (current.some((selected) => selected.id === paper.id)) {
        return current.filter((selected) => selected.id !== paper.id);
      }

      if (current.length >= MAX_SYNTHESIS_SELECTION) {
        return current;
      }

      return [...current, toSelectedSynthesisPaper(paper)];
    });
  }, []);

  const removePaper = useCallback((paperId: number) => {
    setSelectedPapers((current) => current.filter((paper) => paper.id !== paperId));
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedPapers([]);
  }, []);

  const value = useMemo<SynthesisSelectionContextValue>(
    () => ({
      selectedPapers,
      selectedIds,
      selectedCount: selectedPapers.length,
      limit: MAX_SYNTHESIS_SELECTION,
      isSelected,
      canSelectPaper,
      togglePaper,
      removePaper,
      clearSelection,
    }),
    [canSelectPaper, clearSelection, isSelected, removePaper, selectedIds, selectedPapers, togglePaper],
  );

  return <SynthesisSelectionContext.Provider value={value}>{children}</SynthesisSelectionContext.Provider>;
}

function readStoredSelection(): SelectedSynthesisPaper[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const storedSelection = window.localStorage.getItem(SYNTHESIS_SELECTION_STORAGE_KEY);

    return storedSelection ? normalizeSelectedPapers(JSON.parse(storedSelection)) : [];
  } catch {
    return [];
  }
}

function persistSelection(selectedPapers: SelectedSynthesisPaper[]) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(SYNTHESIS_SELECTION_STORAGE_KEY, JSON.stringify(selectedPapers));
  } catch {
    // Browser storage can be unavailable in private or constrained contexts.
  }
}

function normalizeSelectedPapers(value: unknown): SelectedSynthesisPaper[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const seenIds = new Set<number>();
  const selectedPapers: SelectedSynthesisPaper[] = [];

  for (const paper of value) {
    if (!isStoredSelectedPaper(paper) || seenIds.has(paper.id)) {
      continue;
    }

    selectedPapers.push(paper);
    seenIds.add(paper.id);

    if (selectedPapers.length >= MAX_SYNTHESIS_SELECTION) {
      break;
    }
  }

  return selectedPapers;
}

function isStoredSelectedPaper(value: unknown): value is SelectedSynthesisPaper {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "number" &&
    typeof value.arxiv_id === "string" &&
    typeof value.title === "string" &&
    Array.isArray(value.authors) &&
    value.authors.every((author) => typeof author === "string") &&
    typeof value.primary_category === "string" &&
    Array.isArray(value.categories) &&
    value.categories.every((category) => typeof category === "string") &&
    typeof value.published_at === "string" &&
    typeof value.updated_at === "string" &&
    (typeof value.score === "number" || value.score === null)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
