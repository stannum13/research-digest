import {
  AlertCircle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Clock,
  Database,
  History,
  Layers3,
  Loader2,
  Play,
  Search,
  Trash2,
} from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { BackfillJobList } from "../components/BackfillJobList";
import {
  useBackfillJobs,
  useClearSearchCache,
  useClassificationStatus,
  useDeleteSearchCacheEntry,
  useDigestRunDetail,
  useDigestStatus,
  useLatestDigest,
  useRunClassifications,
  useSearchCacheStatus,
  useStats,
} from "../hooks/useDigestApi";
import { formatTimeAgo, formatTimestamp } from "../lib/format";
import type {
  ClassificationStatus,
  DigestRun,
  DigestRunDetail,
  SearchCacheEntry,
  SearchCacheStatusResponse,
} from "../types/api";

const DEFAULT_CLASSIFICATION_LIMIT = "25";

export function StatusPage() {
  const status = useDigestStatus();
  const latestDigest = useLatestDigest();
  const latestRunDetail = useDigestRunDetail(latestDigest.data?.run?.id);
  const backfillJobs = useBackfillJobs();
  const stats = useStats();
  const classificationStatus = useClassificationStatus();
  const searchCacheStatus = useSearchCacheStatus();

  return (
    <div className="space-y-5">
      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <p className="mb-2 font-mono text-xs uppercase text-[var(--text-faint)]">Run Status</p>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-serif text-3xl text-[var(--text-ink)]">{status.data?.status ?? "idle"}</h1>
              <StatusBadge status={status.data?.status ?? "idle"} />
            </div>
          </div>
          <Clock className="text-[var(--accent-clay)]" size={28} aria-hidden="true" />
        </div>
        <p className="text-[var(--text-note)]">Last run: {formatTimestamp(status.data?.last_run_at)}</p>
        <p className="mt-1 font-mono text-[11px] text-[var(--text-faint)]">
          {status.data?.papers_summarized_today ?? 0} summaries today · updated {formatTimeAgo(status.data?.last_run_at)}
        </p>
        {status.data?.error_message ? (
          <p className="mt-4 flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
            <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
            {status.data.error_message}
          </p>
        ) : null}
      </section>

      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="mb-2 font-mono text-xs uppercase text-[var(--text-faint)]">Latest Successful Run</p>
            <h2 className="font-serif text-3xl text-[var(--text-ink)]">
              {latestDigest.data?.run ? `Run #${latestDigest.data.run.id}` : "No run yet"}
            </h2>
          </div>
          <CalendarClock className="text-[var(--accent-lavender)]" size={28} aria-hidden="true" />
        </div>

        {latestDigest.isLoading ? (
          <p className="font-mono text-xs text-[var(--text-faint)]">Loading run detail...</p>
        ) : latestDigest.isError ? (
          <p className="rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
            Latest run detail is unavailable.
          </p>
        ) : latestDigest.data?.run ? (
          <RunDetail
            run={latestDigest.data.run}
            detail={latestRunDetail.data}
            detailError={latestRunDetail.isError}
            detailLoading={latestRunDetail.isFetching}
            paperCount={latestDigest.data.papers.length}
          />
        ) : (
          <p className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 text-sm text-[var(--text-note)]">
            Successful run detail will appear after the first completed digest.
          </p>
        )}
      </section>

      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="mb-2 font-mono text-xs uppercase text-[var(--text-faint)]">Library</p>
            <h2 className="font-serif text-3xl text-[var(--text-ink)]">{stats.data?.papers_total ?? 0} papers</h2>
          </div>
          <Database className="text-[var(--accent-sage)]" size={28} aria-hidden="true" />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Summarized" value={stats.data?.papers_summarized ?? 0} />
          <Stat label="Saved" value={stats.data?.papers_saved ?? 0} />
          <Stat label="Feedback" value={stats.data?.feedback_total ?? 0} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Stat label="LLM calls" value={stats.data?.llm_calls_total ?? 0} />
          <Stat label="LLM tokens" value={stats.data?.llm_tokens_total ?? 0} />
          <Stat label="Est. LLM cost" value={`$${(stats.data?.estimated_llm_cost_usd ?? 0).toFixed(4)}`} />
        </div>
      </section>

      <SearchCacheMaintenance
        isError={searchCacheStatus.isError}
        isFetching={searchCacheStatus.isFetching}
        isLoading={searchCacheStatus.isLoading}
        onRetry={() => void searchCacheStatus.refetch()}
        status={searchCacheStatus.data}
      />

      <ClassificationCoverage
        isError={classificationStatus.isError}
        isFetching={classificationStatus.isFetching}
        isLoading={classificationStatus.isLoading}
        onRetry={() => void classificationStatus.refetch()}
        status={classificationStatus.data}
      />

      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
        <div className="mb-4 flex items-center gap-2 font-mono text-xs uppercase text-[var(--text-faint)]">
          <BarChart3 size={15} aria-hidden="true" />
          Categories
        </div>
        <div className="grid gap-2">
          {Object.entries(stats.data?.categories ?? {}).map(([categoryName, count]) => (
            <div key={categoryName} className="flex items-center justify-between border-b border-[var(--border-warm)] py-2">
              <span className="font-mono text-xs text-[var(--text-note)]">{categoryName}</span>
              <span className="font-mono text-xs text-[var(--text-faint)]">{count}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
        <div className="mb-4 flex items-center gap-2 font-mono text-xs uppercase text-[var(--text-faint)]">
          <History size={15} aria-hidden="true" />
          Run History
        </div>
        <div className="grid gap-2">
          <CapabilityRow label="Archive date picker" status="Available" active />
          <CapabilityRow label="Date-targeted digest run" status="Available" active />
          <CapabilityRow
            label="Latest run detail"
            status={latestRunDetail.data ? "Available" : latestDigest.data?.run ? "Loading" : "Waiting"}
            active={Boolean(latestRunDetail.data)}
          />
          <CapabilityRow
            label="Backfill job list"
            status={backfillJobs.data ? `${backfillJobs.data.total} tracked` : "Loading"}
            active={Boolean(backfillJobs.data)}
          />
          <CapabilityRow
            label="Search cache"
            status={
              searchCacheStatus.data
                ? `${searchCacheStatus.data.total_entries} entries`
                : searchCacheStatus.isError
                  ? "Unavailable"
                  : "Loading"
            }
            active={Boolean(searchCacheStatus.data)}
          />
          <CapabilityRow
            label="Classification coverage"
            status={
              classificationStatus.data
                ? `${formatCoveragePercent(classificationStatus.data.coverage_percentage)} covered`
                : classificationStatus.isError
                  ? "Unavailable"
                  : "Loading"
            }
            active={Boolean(classificationStatus.data)}
          />
        </div>
        <div className="mt-4 border-t border-[var(--border-warm)] pt-4">
          <div className="mb-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">Recent Backfills</div>
          <BackfillJobList jobs={backfillJobs.data?.items ?? []} emptyMessage="No backfill jobs tracked yet." />
        </div>
      </section>
    </div>
  );
}

function SearchCacheMaintenance({
  isError,
  isFetching,
  isLoading,
  onRetry,
  status,
}: {
  isError: boolean;
  isFetching: boolean;
  isLoading: boolean;
  onRetry: () => void;
  status?: SearchCacheStatusResponse;
}) {
  const clearCache = useClearSearchCache();
  const deleteEntry = useDeleteSearchCacheEntry();
  const [feedback, setFeedback] = useState<string | null>(null);
  const entries = status?.entries ?? [];
  const mutationPending = clearCache.isPending || deleteEntry.isPending;
  const clearDisabled = mutationPending || isLoading || isError || (status?.total_entries ?? 0) === 0;
  const errorMessage = clearCache.isError
    ? `Clear failed: ${clearCache.error.message || "Search cache clear request failed."}`
    : deleteEntry.isError
      ? `Delete failed: ${deleteEntry.error.message || "Search cache delete request failed."}`
      : null;

  function clearAll() {
    setFeedback(null);
    clearCache.mutate(undefined, {
      onSuccess: (response) => {
        setFeedback(`Cleared ${formatCacheEntryCount(response.deleted_count)}.`);
      },
    });
  }

  function deleteCachedEntry(cacheId: number) {
    setFeedback(null);
    deleteEntry.mutate(cacheId, {
      onSuccess: (response) => {
        setFeedback(`Deleted ${formatCacheEntryCount(response.deleted_count)}.`);
      },
    });
  }

  return (
    <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-2 font-mono text-xs uppercase text-[var(--text-faint)]">Search Cache</p>
          <h2 className="font-serif text-3xl text-[var(--text-ink)]">
            {status?.cache_version ?? "Loading"}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-[var(--text-faint)]">
            {isFetching && !isLoading ? "Refreshing cache..." : "Normalized retrieval responses"}
          </p>
        </div>
        <Search className="text-[var(--accent-clay)]" size={28} aria-hidden="true" />
      </div>

      {isLoading ? (
        <p className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 font-mono text-xs text-[var(--text-faint)]">
          Loading search cache status...
        </p>
      ) : isError ? (
        <div className="rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
          <div className="flex gap-2">
            <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
            Search cache status is unavailable.
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex min-h-9 items-center justify-center rounded-full border border-[var(--accent-clay)] px-3 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Stat label="Total entries" value={status?.total_entries ?? 0} />
        <Stat label="Total hits" value={status?.total_hits ?? 0} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          aria-label="Clear all search cache entries"
          onClick={clearAll}
          disabled={clearDisabled}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {clearCache.isPending ? (
            <Loader2 className="animate-spin" size={15} aria-hidden="true" />
          ) : (
            <Trash2 size={14} aria-hidden="true" />
          )}
          {clearCache.isPending ? "Clearing..." : "Clear cache"}
        </button>
        <p className="font-mono text-[11px] text-[var(--text-faint)]">
          Current version entries only.
        </p>
      </div>

      {feedback ? (
        <p
          role="status"
          aria-live="polite"
          className="mt-3 rounded-lg border border-[rgba(127,155,122,0.28)] bg-[rgba(127,155,122,0.08)] p-3 font-mono text-xs text-[var(--text-note)]"
        >
          {feedback}
        </p>
      ) : null}

      {errorMessage ? (
        <p
          role="alert"
          className="mt-3 flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]"
        >
          <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
          {errorMessage}
        </p>
      ) : null}

      <div className="mt-5 overflow-x-auto border-t border-[var(--border-warm)] pt-4">
        <table className="min-w-full text-left">
          <caption className="sr-only">Recent search cache entries</caption>
          <thead>
            <tr className="border-b border-[var(--border-warm)] font-mono text-[11px] uppercase text-[var(--text-faint)]">
              <th scope="col" className="pb-2 pr-4 font-normal">Normalized query</th>
              <th scope="col" className="pb-2 pr-4 font-normal">Filter</th>
              <th scope="col" className="pb-2 pr-4 text-right font-normal">Limit</th>
              <th scope="col" className="pb-2 pr-4 text-right font-normal">Results</th>
              <th scope="col" className="pb-2 pr-4 text-right font-normal">Hits</th>
              <th scope="col" className="pb-2 text-right font-normal">Action</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const entryPending = deleteEntry.isPending && deleteEntry.variables === entry.id;

              return (
                <tr key={entry.id} className="border-b border-[var(--border-warm)] last:border-b-0">
                  <td className="max-w-[18rem] py-3 pr-4 align-top">
                    <div className="break-words font-mono text-xs text-[var(--text-note)]">
                      {formatCacheQuery(entry.normalized_q)}
                    </div>
                    <div className="mt-1 font-mono text-[10px] uppercase text-[var(--text-faint)]">
                      Updated {formatTimeAgo(entry.updated_at)}
                    </div>
                  </td>
                  <td className="py-3 pr-4 align-top font-mono text-xs text-[var(--text-note)]">
                    {formatCacheFilter(entry)}
                  </td>
                  <td className="py-3 pr-4 text-right align-top font-mono text-xs text-[var(--text-faint)]">
                    {entry.limit}
                  </td>
                  <td className="py-3 pr-4 text-right align-top font-mono text-xs text-[var(--text-faint)]">
                    {entry.result_count}
                  </td>
                  <td className="py-3 pr-4 text-right align-top font-mono text-xs text-[var(--text-faint)]">
                    {entry.hit_count}
                  </td>
                  <td className="py-3 text-right align-top">
                    <button
                      type="button"
                      aria-label={`Delete search cache entry ${entry.id}`}
                      onClick={() => deleteCachedEntry(entry.id)}
                      disabled={mutationPending || isLoading || isError}
                      className="inline-flex min-h-9 items-center justify-center gap-2 rounded-full border border-[var(--border-warm)] px-3 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {entryPending ? (
                        <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                      ) : (
                        <Trash2 size={13} aria-hidden="true" />
                      )}
                      {entryPending ? "Deleting..." : "Delete"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!entries.length && !isLoading ? (
          <p className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 text-sm text-[var(--text-note)]">
            No search cache entries yet.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function ClassificationCoverage({
  isError,
  isFetching,
  isLoading,
  onRetry,
  status,
}: {
  isError: boolean;
  isFetching: boolean;
  isLoading: boolean;
  onRetry: () => void;
  status?: ClassificationStatus;
}) {
  const runClassifications = useRunClassifications();
  const [limit, setLimit] = useState(DEFAULT_CLASSIFICATION_LIMIT);
  const [onlyMissing, setOnlyMissing] = useState(true);
  const trimmedLimit = limit.trim();
  const parsedLimit = trimmedLimit ? Number(trimmedLimit) : undefined;
  const limitInvalid =
    trimmedLimit !== "" &&
    (!Number.isInteger(parsedLimit) || (parsedLimit ?? 0) < 1 || (parsedLimit ?? 0) > 1000);
  const summarizedCount = status?.summarized_paper_count ?? 0;
  const classifiedCount = status?.classified_paper_count ?? 0;
  const missingCount = Math.max(summarizedCount - classifiedCount, 0);
  const noSummaries = Boolean(status) && summarizedCount === 0;
  const noMissing = Boolean(status) && onlyMissing && missingCount === 0;
  const runDisabled =
    runClassifications.isPending || isLoading || isError || limitInvalid || noSummaries || noMissing;
  const labelTypeCounts = Object.entries(status?.label_type_counts ?? {});

  function submitRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (runDisabled) {
      return;
    }

    runClassifications.mutate({
      limit: parsedLimit,
      only_missing: onlyMissing,
    });
  }

  return (
    <section className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-2 font-mono text-xs uppercase text-[var(--text-faint)]">Ontology Coverage</p>
          <h2 className="font-serif text-3xl text-[var(--text-ink)]">
            {status ? formatCoveragePercent(status.coverage_percentage) : "Loading"}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-[var(--text-faint)]">
            {isFetching && !isLoading ? "Refreshing coverage..." : `${missingCount} missing classifications`}
          </p>
        </div>
        <Layers3 className="text-[var(--accent-plum)]" size={28} aria-hidden="true" />
      </div>

      {isLoading ? (
        <p className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 font-mono text-xs text-[var(--text-faint)]">
          Loading classification coverage...
        </p>
      ) : isError ? (
        <div className="rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
          <div className="flex gap-2">
            <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
            Classification coverage is unavailable.
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex min-h-9 items-center justify-center rounded-full border border-[var(--accent-clay)] px-3 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <Stat label="Summarized papers" value={summarizedCount} />
        <Stat label="Classified papers" value={classifiedCount} />
        <Stat label="Coverage" value={status ? formatCoveragePercent(status.coverage_percentage) : "0%"} />
        <Stat label="Total labels" value={status?.total_labels ?? 0} />
      </div>

      <form onSubmit={submitRun} className="mt-4 grid gap-3 lg:grid-cols-[minmax(8rem,0.5fr)_auto_auto] lg:items-end">
        <label className="grid gap-2">
          <span className="font-mono text-[11px] uppercase text-[var(--text-faint)]">Batch limit</span>
          <input
            aria-label="Classification batch limit"
            type="number"
            min={1}
            max={1000}
            inputMode="numeric"
            value={limit}
            onChange={(event) => setLimit(event.currentTarget.value)}
            placeholder="all"
            className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[rgba(255,250,243,0.75)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)] disabled:opacity-70"
            disabled={runClassifications.isPending}
          />
        </label>

        <label className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] px-3 font-mono text-[11px] uppercase text-[var(--text-faint)]">
          <input
            aria-label="Only missing classifications"
            type="checkbox"
            checked={onlyMissing}
            onChange={(event) => setOnlyMissing(event.currentTarget.checked)}
            className="h-4 w-4 accent-[var(--accent-clay)]"
            disabled={runClassifications.isPending}
          />
          Only missing
        </label>

        <button
          type="submit"
          aria-label={onlyMissing ? "Run missing classifications" : "Run classifications for all summarized papers"}
          disabled={runDisabled}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runClassifications.isPending ? (
            <Loader2 className="animate-spin" size={15} aria-hidden="true" />
          ) : (
            <Play size={14} aria-hidden="true" />
          )}
          {runClassifications.isPending
            ? "Running..."
            : noMissing
              ? "Coverage complete"
              : onlyMissing
                ? "Run missing classifications"
                : "Run classifications"}
        </button>
      </form>

      {limitInvalid ? (
        <p className="mt-2 font-mono text-[11px] text-[var(--accent-rose)]">Use a limit from 1 to 1000, or leave it blank.</p>
      ) : noSummaries ? (
        <p className="mt-2 font-mono text-[11px] text-[var(--text-faint)]">No summarized papers are ready for classification.</p>
      ) : null}

      {runClassifications.data ? (
        <p className="mt-3 rounded-lg border border-[rgba(127,155,122,0.28)] bg-[rgba(127,155,122,0.08)] p-3 font-mono text-xs text-[var(--text-note)]">
          Last batch: {runClassifications.data.papers_processed} papers processed · coverage{" "}
          {formatCoveragePercent(runClassifications.data.status.coverage_percentage)}
        </p>
      ) : null}

      {runClassifications.isError ? (
        <p
          role="alert"
          className="mt-3 flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]"
        >
          <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
          Classification run failed: {runClassifications.error.message || "Run request failed."}
        </p>
      ) : null}

      <div className="mt-5 border-t border-[var(--border-warm)] pt-4">
        <div className="mb-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">Label Type Counts</div>
        {labelTypeCounts.length ? (
          <div className="grid gap-x-4 sm:grid-cols-2">
            {labelTypeCounts.map(([labelType, count]) => (
              <div
                key={labelType}
                className="flex items-center justify-between gap-3 border-b border-[var(--border-warm)] py-2"
              >
                <span className="font-mono text-xs text-[var(--text-note)]">{formatLabelType(labelType)}</span>
                <span className="font-mono text-xs text-[var(--text-faint)]">{count}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 text-sm text-[var(--text-note)]">
            Label counts will appear once coverage is available.
          </p>
        )}
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const failed = status === "failed";
  const running = status === "running" || status === "pending";
  const idle = status === "idle";
  const Icon = failed ? AlertCircle : running || idle ? Clock : CheckCircle2;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[10px] uppercase ${
        failed
          ? "bg-[rgba(199,131,127,0.12)] text-[var(--accent-rose)]"
          : running
            ? "bg-[rgba(196,162,79,0.14)] text-[#8b6b3d]"
            : idle
              ? "bg-[rgba(238,229,216,0.62)] text-[var(--text-faint)]"
              : "bg-[rgba(127,155,122,0.12)] text-[var(--accent-sage)]"
      }`}
    >
      <Icon size={12} aria-hidden="true" />
      {status}
    </span>
  );
}

function RunDetail({
  detail,
  detailError,
  detailLoading,
  paperCount,
  run,
}: {
  detail?: DigestRunDetail;
  detailError: boolean;
  detailLoading: boolean;
  paperCount: number;
  run: DigestRun;
}) {
  const categoryScope = run.category_scope.length ? run.category_scope.join(", ") : "all categories";

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Fetched" value={run.papers_fetched} />
        <Stat label="New" value={run.papers_new} />
        <Stat label="Summarized" value={run.papers_summarized} />
        <Stat label="Visible papers" value={paperCount} />
      </div>
      <div className="grid gap-2 font-mono text-xs text-[var(--text-faint)]">
        <RunTimestamp label="Target date" value={run.target_date ?? "latest feed"} />
        <RunTimestamp label="Categories" value={categoryScope} />
        <RunTimestamp label="Started" value={formatTimestamp(run.started_at)} />
        <RunTimestamp label="Completed" value={formatTimestamp(run.completed_at)} />
      </div>
      {detailLoading ? (
        <p className="font-mono text-xs text-[var(--text-faint)]">Loading run accounting...</p>
      ) : null}
      {detailError ? (
        <p className="rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
          Run accounting is unavailable.
        </p>
      ) : null}
      {detail ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="LLM calls" value={detail.llm_calls.length} />
          <Stat label="LLM tokens" value={detail.llm_tokens_total} />
          <Stat label="Run cost" value={`$${detail.estimated_llm_cost_usd.toFixed(4)}`} />
        </div>
      ) : null}
      {run.error_message ? (
        <p className="flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-3 text-sm text-[var(--text-note)]">
          <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
          {run.error_message}
        </p>
      ) : null}
    </div>
  );
}

function RunTimestamp({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border-warm)] py-2">
      <span>{label}</span>
      <span className="text-right text-[var(--text-note)]">{value}</span>
    </div>
  );
}

function CapabilityRow({ active = false, label, status }: { active?: boolean; label: string; status: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border-warm)] py-2 last:border-b-0">
      <span className="text-sm text-[var(--text-note)]">{label}</span>
      <span
        className={`rounded-full px-2.5 py-1 font-mono text-[10px] uppercase ${
          active ? "bg-[rgba(127,155,122,0.12)] text-[var(--accent-sage)]" : "bg-[rgba(238,229,216,0.62)] text-[var(--text-faint)]"
        }`}
      >
        {status}
      </span>
    </div>
  );
}

function formatCoveragePercent(value: number): string {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

function formatLabelType(labelType: string): string {
  const spaced = labelType.replace(/_/g, " ");
  return `${spaced.charAt(0).toUpperCase()}${spaced.slice(1)}`;
}

function formatCacheQuery(query: string): string {
  return query || "Any query";
}

function formatCacheFilter(entry: SearchCacheEntry): string {
  const labelType = entry.normalized_label_type;
  const label = entry.normalized_label;

  if (labelType && label) {
    return `${formatLabelType(labelType)} / ${label}`;
  }

  if (labelType) {
    return `${formatLabelType(labelType)} / any label`;
  }

  if (label) {
    return `Any type / ${label}`;
  }

  return "All labels";
}

function formatCacheEntryCount(count: number): string {
  return `${count.toLocaleString()} ${count === 1 ? "cache entry" : "cache entries"}`;
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-4">
      <div className="font-serif text-2xl text-[var(--text-ink)]">{value}</div>
      <div className="font-mono text-[11px] uppercase text-[var(--text-faint)]">{label}</div>
    </div>
  );
}
