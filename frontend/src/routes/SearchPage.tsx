import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Filter, Loader2, Search, X } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { DigestHeader } from "../components/DigestHeader";
import { EmptyState } from "../components/EmptyState";
import { SkeletonCard } from "../components/SkeletonCard";
import { TagChip } from "../components/TagChip";
import { useSearch } from "../hooks/useDigestApi";
import { formatShortDate, sentenceList } from "../lib/format";
import type { PaperWithBreakdown, SearchQueryParams, SearchResult } from "../types/api";

const LABEL_TYPE_OPTIONS = [
  "method_family",
  "evidence_type",
  "caveat_class",
  "task",
  "dataset_or_benchmark",
  "architecture_primitive",
  "probe_family",
];

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeParams = useMemo(() => searchParamsToQuery(searchParams), [searchParams]);
  const [draftQuery, setDraftQuery] = useState(activeParams.q ?? "");
  const [draftLabelType, setDraftLabelType] = useState(activeParams.label_type ?? "");
  const [draftLabel, setDraftLabel] = useState(activeParams.label ?? "");
  const searchQuery = useSearch(activeParams);
  const results = searchQuery.data?.items ?? [];
  const hasActiveSearch = hasSearchInput(activeParams);
  const total = searchQuery.data?.total ?? results.length;
  const categoryCount = countCategories(results.map((result) => result.paper));

  useEffect(() => {
    setDraftQuery(activeParams.q ?? "");
    setDraftLabelType(activeParams.label_type ?? "");
    setDraftLabel(activeParams.label ?? "");
  }, [activeParams.label, activeParams.label_type, activeParams.q]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearchParams(queryToSearchParams({
      q: draftQuery.trim(),
      label_type: draftLabelType.trim(),
      label: draftLabel.trim(),
    }));
  }

  function clearSearch() {
    setDraftQuery("");
    setDraftLabelType("");
    setDraftLabel("");
    setSearchParams(new URLSearchParams());
  }

  return (
    <>
      <DigestHeader
        title="Search"
        headline="Retrieval"
        total={total}
        categoryCount={categoryCount}
        meta={hasActiveSearch ? `${total} results · ${categoryCount} categories` : "Ready"}
        action={null}
      />

      <section className="mb-6 rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.72)] p-4 shadow-card sm:p-5">
        <form onSubmit={submitSearch} className="grid gap-4">
          <label className="grid gap-2">
            <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
              <Search size={14} aria-hidden="true" />
              Query
            </span>
            <input
              aria-label="Search query"
              type="search"
              value={draftQuery}
              onChange={(event) => setDraftQuery(event.currentTarget.value)}
              placeholder="agent evaluation"
              className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)_auto] sm:items-end">
            <label className="grid gap-2">
              <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
                <Filter size={14} aria-hidden="true" />
                Label type
              </span>
              <input
                aria-label="Label type"
                list="search-label-types"
                value={draftLabelType}
                onChange={(event) => setDraftLabelType(event.currentTarget.value)}
                placeholder="method_family"
                className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              />
              <datalist id="search-label-types">
                {LABEL_TYPE_OPTIONS.map((labelType) => (
                  <option key={labelType} value={labelType} />
                ))}
              </datalist>
            </label>

            <label className="grid gap-2">
              <span className="font-mono text-[11px] uppercase text-[var(--text-faint)]">Label</span>
              <input
                aria-label="Label"
                value={draftLabel}
                onChange={(event) => setDraftLabel(event.currentTarget.value)}
                placeholder="retrieval"
                className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              />
            </label>

            <div className="flex gap-2">
              <button
                type="submit"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
              >
                {searchQuery.isFetching ? (
                  <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
                    <Loader2 size={15} aria-hidden="true" />
                  </motion.span>
                ) : (
                  <Search size={15} aria-hidden="true" />
                )}
                Search
              </button>
              <button
                type="button"
                onClick={clearSearch}
                className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-[var(--border-warm)] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
                aria-label="Clear search"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
        </form>
      </section>

      {!hasActiveSearch ? (
        <EmptyState title="No query submitted." />
      ) : searchQuery.isLoading ? (
        <div className="space-y-5">
          {Array.from({ length: 3 }, (_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : searchQuery.isError ? (
        <SearchUnavailable onRetry={() => void searchQuery.refetch()} />
      ) : results.length === 0 ? (
        <EmptyState title="No matches found." />
      ) : (
        <motion.div layout className="space-y-5">
          <AnimatePresence>
            {results.map((result, index) => (
              <SearchResultCard key={result.paper.arxiv_id} result={result} index={index} />
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </>
  );
}

function SearchResultCard({ result, index }: { result: SearchResult; index: number }) {
  const { paper } = result;
  const summary = paper.breakdown?.one_line_takeaway ?? paper.abstract;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
      className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-5 shadow-card transition-colors hover:border-[rgba(183,119,85,0.5)] sm:p-6"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-warm)] pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <TagChip tone="category" category={paper.primary_category}>
            {paper.primary_category}
          </TagChip>
          <span className="rounded-full bg-[rgba(238,229,216,0.72)] px-2.5 py-1 font-mono text-[10px] uppercase text-[var(--text-note)]">
            Score {formatScore(result.score)}
          </span>
        </div>
        <div className="font-mono text-[11px] text-[var(--text-faint)]">
          {formatShortDate(paper.published_at)} · {paper.arxiv_id}
        </div>
      </div>

      <h2 className="mb-3 [overflow-wrap:anywhere] font-serif text-[26px] font-medium leading-[1.25] text-[var(--text-ink)]">
        {paper.title}
      </h2>
      <p className="mb-4 font-mono text-[11px] leading-relaxed text-[var(--text-faint)]">
        {sentenceList(paper.authors, 4)} · updated {formatShortDate(paper.updated_at)}
      </p>

      <p className="mb-4 border-y border-[var(--border-warm)] py-4 text-[16px] italic leading-7 text-[var(--text-note)]">
        {summary}
      </p>

      <div className="mb-4 rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.45)] p-3">
        <div className="mb-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">Reason</div>
        <p className="text-sm text-[var(--text-note)]">{result.reason || "Matched retrieval index."}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <MatchGroup label="Matched fields" values={result.matched_fields} />
        <MatchGroup label="Matched labels" values={result.matched_labels} />
      </div>

      <div className="mt-5 flex justify-end">
        <a
          href={paper.arxiv_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
        >
          Open arXiv
          <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>
    </motion.article>
  );
}

function MatchGroup({ label, values }: { label: string; values: string[] }) {
  const visibleValues = values.filter(Boolean);

  return (
    <div>
      <div className="mb-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">{label}</div>
      <div className="flex flex-wrap gap-2">
        {visibleValues.length ? (
          visibleValues.map((value) => <TagChip key={value}>{value}</TagChip>)
        ) : (
          <span className="font-mono text-[11px] text-[var(--text-faint)]">None</span>
        )}
      </div>
    </div>
  );
}

function SearchUnavailable({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-[14px] border border-[rgba(199,131,127,0.45)] bg-[rgba(255,250,243,0.72)] p-6 text-[var(--text-note)] shadow-card">
      <h2 className="mb-2 font-serif text-2xl text-[var(--text-ink)]">Search is unavailable.</h2>
      <button
        className="mt-3 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
        type="button"
        onClick={onRetry}
      >
        Try again
      </button>
    </div>
  );
}

function searchParamsToQuery(searchParams: URLSearchParams): SearchQueryParams {
  return {
    q: cleanParam(searchParams.get("q")),
    label_type: cleanParam(searchParams.get("label_type")),
    label: cleanParam(searchParams.get("label")),
  };
}

function queryToSearchParams(query: SearchQueryParams): URLSearchParams {
  const searchParams = new URLSearchParams();

  if (query.q) {
    searchParams.set("q", query.q);
  }

  if (query.label_type) {
    searchParams.set("label_type", query.label_type);
  }

  if (query.label) {
    searchParams.set("label", query.label);
  }

  return searchParams;
}

function cleanParam(value: string | null): string | undefined {
  const cleanValue = value?.trim();
  return cleanValue ? cleanValue : undefined;
}

function hasSearchInput(params: SearchQueryParams): boolean {
  return Boolean(params.q || params.label_type || params.label);
}

function countCategories(papers: PaperWithBreakdown[]): number {
  return new Set(papers.flatMap((paper) => paper.categories)).size;
}

function formatScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(2);
}
