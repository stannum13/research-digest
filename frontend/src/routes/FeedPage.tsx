import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";

import { DigestHeader } from "../components/DigestHeader";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { PaperCard } from "../components/PaperCard";
import { SkeletonCard } from "../components/SkeletonCard";
import { flattenPapers, usePapers } from "../hooks/useDigestApi";
import { isWithinLastDays, toIsoDate } from "../lib/format";
import type { FilterId } from "../lib/tags";
import type { PaperQueryParams, PaperWithBreakdown } from "../types/api";

type FeedPageProps = {
  title: string;
  category?: string;
  savedOnly?: boolean;
};

export function FeedPage({ title, category, savedOnly = false }: FeedPageProps) {
  const [filter, setFilter] = useState<FilterId>(savedOnly ? "saved" : "all");
  const params = useMemo<PaperQueryParams>(() => {
    const selectedCategory = isCategoryFilter(filter) ? filter : category;
    return {
      category: selectedCategory,
      saved: savedOnly || filter === "saved" ? true : undefined,
      date: filter === "today" ? toIsoDate() : undefined,
    };
  }, [category, filter, savedOnly]);

  const papersQuery = usePapers(params);
  const papers = useMemo(() => {
    const flattened = flattenPapers(papersQuery.data);
    if (filter === "week") {
      return flattened.filter((paper) => isWithinLastDays(paper.published_at, 7));
    }
    return flattened;
  }, [papersQuery.data, filter]);

  const firstPage = papersQuery.data?.pages[0];
  const categoryCount = countCategories(papers);

  return (
    <>
      <DigestHeader
        title={title}
        total={firstPage?.total ?? papers.length}
        categoryCount={categoryCount}
        status={firstPage?.digest_status}
      />
      <FilterBar selected={filter} onSelect={setFilter} />

      {papersQuery.isLoading ? (
        <div className="space-y-5">
          {Array.from({ length: 5 }, (_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : papersQuery.isError ? (
        <ErrorState onRetry={() => void papersQuery.refetch()} />
      ) : papers.length === 0 ? (
        <EmptyState />
      ) : (
        <motion.div layout className="space-y-5">
          <AnimatePresence>
            {papers.map((paper, index) => (
              <PaperCard key={paper.arxiv_id} paper={paper} index={index} />
            ))}
          </AnimatePresence>

          {papersQuery.hasNextPage ? (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={() => void papersQuery.fetchNextPage()}
                disabled={papersQuery.isFetchingNextPage}
                className="rounded-full border border-[var(--border-warm)] bg-[rgba(255,250,243,0.64)] px-5 py-3 font-mono text-xs text-[var(--text-note)] shadow-card transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
              >
                {papersQuery.isFetchingNextPage ? "Loading..." : "Load more"}
              </button>
            </div>
          ) : null}
        </motion.div>
      )}
    </>
  );
}

function isCategoryFilter(filter: FilterId): filter is "cs.AI" | "cs.LG" | "cs.CL" | "cs.CV" | "stat.ML" | "quant-ph" {
  return ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML", "quant-ph"].includes(filter);
}

function countCategories(papers: PaperWithBreakdown[]): number {
  return new Set(papers.flatMap((paper) => paper.categories)).size;
}
