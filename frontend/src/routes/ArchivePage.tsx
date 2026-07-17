import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  CalendarClock,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Clock3,
  Database,
  History,
  Loader2,
  Play,
  type LucideIcon,
  RotateCcw,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { BackfillJobList } from "../components/BackfillJobList";
import { DigestHeader } from "../components/DigestHeader";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { PaperCard } from "../components/PaperCard";
import { SkeletonCard } from "../components/SkeletonCard";
import { flattenPapers, useBackfillJobs, useBackfillRange, usePapers } from "../hooks/useDigestApi";
import { addIsoDateDays, dateFromIsoDate, formatArchiveDate, toIsoDate } from "../lib/format";
import type { BackfillJob, PaperQueryParams, PaperWithBreakdown } from "../types/api";

const ARCHIVE_CATEGORIES = ["all", "cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML", "quant-ph"] as const;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const MAX_BACKFILL_DAYS = 7;

type ArchiveCategory = (typeof ARCHIVE_CATEGORIES)[number];

export function ArchivePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const today = toIsoDate();
  const selectedDate = getArchiveDate(searchParams.get("date"), today);
  const selectedCategory = getArchiveCategory(searchParams.get("category"));
  const [backfillStart, setBackfillStart] = useState(selectedDate);
  const [backfillEnd, setBackfillEnd] = useState(selectedDate);

  const params = useMemo<PaperQueryParams>(
    () => ({
      date: selectedDate,
      category: selectedCategory === "all" ? undefined : selectedCategory,
    }),
    [selectedCategory, selectedDate],
  );

  const papersQuery = usePapers(params);
  const papers = useMemo(() => flattenPapers(papersQuery.data), [papersQuery.data]);
  const firstPage = papersQuery.data?.pages[0];
  const total = firstPage?.total ?? papers.length;
  const categoryCount = countCategories(papers);
  const canMoveForward = selectedDate < today;
  const backfillRange = useBackfillRange();
  const backfillJobs = useBackfillJobs();
  const backfillRangeError = getBackfillRangeError(backfillStart, backfillEnd, today);
  const backfillDayCount = countIsoDateDays(backfillStart, backfillEnd);
  const categoryScope = selectedCategory === "all" ? undefined : [selectedCategory];
  const categoryScopeLabel = selectedCategory === "all" ? "all categories" : selectedCategory;
  const recentBackfillJobs = useMemo(
    () => mergeBackfillJobs(backfillRange.data, backfillJobs.data?.items ?? []),
    [backfillJobs.data?.items, backfillRange.data],
  );

  useEffect(() => {
    setBackfillStart(selectedDate);
    setBackfillEnd(selectedDate);
  }, [selectedDate]);

  function updateArchive(next: { date?: string; category?: ArchiveCategory }) {
    const nextParams = new URLSearchParams(searchParams);

    if (next.date) {
      nextParams.set("date", next.date);
    }

    if (next.category) {
      if (next.category === "all") {
        nextParams.delete("category");
      } else {
        nextParams.set("category", next.category);
      }
    }

    setSearchParams(nextParams);
  }

  function requestSelectedDateBackfill() {
    if (getBackfillRangeError(selectedDate, selectedDate, today)) {
      return;
    }

    backfillRange.mutate({
      start_date: selectedDate,
      end_date: selectedDate,
      category_scope: categoryScope,
    });
  }

  function requestBackfillRange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (backfillRangeError) {
      return;
    }

    backfillRange.mutate({
      start_date: backfillStart,
      end_date: backfillEnd,
      category_scope: categoryScope,
    });
  }

  return (
    <>
      <DigestHeader
        title="Archive"
        headline={formatArchiveDate(selectedDate)}
        total={total}
        categoryCount={categoryCount}
        status={firstPage?.digest_status}
        meta={`${total} papers · ${categoryCount} categories · ${selectedDate}`}
        action={
          <BackfillHeaderAction
            disabled={backfillRange.isPending}
            running={backfillRange.isPending}
            onClick={requestSelectedDateBackfill}
          />
        }
      />

      <section className="mb-6 rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.72)] p-4 shadow-card sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <label className="grid flex-1 gap-2">
            <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
              <CalendarDays size={14} aria-hidden="true" />
              Archive date
            </span>
            <input
              aria-label="Archive date"
              type="date"
              value={selectedDate}
              max={today}
              onChange={(event) => updateArchive({ date: event.currentTarget.value })}
              className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
            />
          </label>

          <div className="flex items-center gap-2">
            <ArchiveIconButton
              label="Previous day"
              onClick={() => updateArchive({ date: addIsoDateDays(selectedDate, -1) })}
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </ArchiveIconButton>
            <ArchiveIconButton
              label="Next day"
              disabled={!canMoveForward}
              onClick={() => updateArchive({ date: addIsoDateDays(selectedDate, 1) })}
            >
              <ChevronRight size={16} aria-hidden="true" />
            </ArchiveIconButton>
            <button
              type="button"
              onClick={() => updateArchive({ date: today })}
              className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[var(--border-warm)] px-3.5 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
            >
              <RotateCcw size={14} aria-hidden="true" />
              Today
            </button>
          </div>
        </div>

        <div className="scrollbar-soft -mx-1 mt-4 flex gap-2 overflow-x-auto px-1 pb-1">
          {ARCHIVE_CATEGORIES.map((category) => {
            const active = selectedCategory === category;
            return (
              <button
                key={category}
                type="button"
                onClick={() => updateArchive({ category })}
                className={`shrink-0 rounded-full border px-3.5 py-2 font-mono text-[11px] transition ${
                  active
                    ? "border-[var(--accent-clay)] bg-[var(--accent-clay)] text-[var(--bg-card)]"
                    : "border-[var(--border-warm)] bg-[rgba(255,250,243,0.58)] text-[var(--text-note)] hover:border-[var(--accent-clay)]"
                }`}
              >
                {category === "all" ? "All" : category}
              </button>
            );
          })}
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <ArchiveSignal
            icon={Database}
            label="Date query"
            value={papersQuery.isFetching ? "Refreshing" : "Live"}
            active
          />
          <ArchiveSignal
            icon={CalendarClock}
            label="Backfill jobs"
            value={backfillRange.isPending ? "Submitting" : "Ready"}
            active
          />
          <ArchiveSignal
            icon={History}
            label="Job table"
            value={backfillJobs.data ? `${backfillJobs.data.total} tracked` : "Loading"}
            active={Boolean(backfillJobs.data?.total)}
          />
        </div>

        <form onSubmit={requestBackfillRange} className="mt-5 border-t border-[var(--border-warm)] pt-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <label className="grid flex-1 gap-2">
              <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
                <CalendarClock size={14} aria-hidden="true" />
                Backfill from
              </span>
              <input
                aria-label="Backfill from"
                type="date"
                value={backfillStart}
                max={today}
                onChange={(event) => setBackfillStart(event.currentTarget.value)}
                className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              />
            </label>

            <label className="grid flex-1 gap-2">
              <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
                <CalendarClock size={14} aria-hidden="true" />
                Backfill to
              </span>
              <input
                aria-label="Backfill to"
                type="date"
                value={backfillEnd}
                max={today}
                min={backfillStart}
                onChange={(event) => setBackfillEnd(event.currentTarget.value)}
                className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              />
            </label>

            <button
              type="submit"
              disabled={backfillRange.isPending || Boolean(backfillRangeError)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-not-allowed disabled:border-[var(--border-warm)] disabled:text-[var(--text-faint)] disabled:hover:bg-transparent"
            >
              {backfillRange.isPending ? (
                <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
                  <Loader2 size={15} aria-hidden="true" />
                </motion.span>
              ) : (
                <Play size={14} aria-hidden="true" />
              )}
              {backfillRange.isPending ? "Submitting..." : "Start backfill"}
            </button>
          </div>

          <div
            aria-live="polite"
            className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-[11px] text-[var(--text-faint)]"
          >
            {backfillRangeError ? (
              <span className="inline-flex items-center gap-1.5 text-[var(--accent-rose)]">
                <AlertCircle size={13} aria-hidden="true" />
                {backfillRangeError}
              </span>
            ) : (
              <span>
                {backfillDayCount} {backfillDayCount === 1 ? "day" : "days"} · {categoryScopeLabel}
              </span>
            )}
            {backfillRange.isError ? (
              <span className="inline-flex items-center gap-1.5 text-[var(--accent-rose)]">
                <AlertCircle size={13} aria-hidden="true" />
                Backfill request failed.
              </span>
            ) : null}
            {backfillRange.data ? (
              <span className="inline-flex items-center gap-1.5 text-[var(--accent-sage)]">
                <CheckCircle2 size={13} aria-hidden="true" />
                Job #{backfillRange.data.id} queued for {backfillRange.data.total_days}{" "}
                {backfillRange.data.total_days === 1 ? "day" : "days"}
              </span>
            ) : null}
          </div>

          <BackfillJobList className="mt-3" jobs={recentBackfillJobs} emptyMessage="No backfill jobs tracked yet." />
        </form>
      </section>

      {papersQuery.isLoading ? (
        <div className="space-y-5">
          {Array.from({ length: 5 }, (_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : papersQuery.isError ? (
        <ErrorState onRetry={() => void papersQuery.refetch()} />
      ) : papers.length === 0 ? (
        <EmptyState
          title="No papers for this date."
          detail="Backfilled summaries will appear here when the backend has data for the selected day."
        />
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

function BackfillHeaderAction({
  disabled,
  onClick,
  running,
}: {
  disabled: boolean;
  onClick: () => void;
  running: boolean;
}) {
  return (
    <button
      type="button"
      aria-label="Run selected archive date"
      disabled={disabled}
      onClick={onClick}
      className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-wait disabled:opacity-70"
    >
      {running ? (
        <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
          <Loader2 size={15} aria-hidden="true" />
        </motion.span>
      ) : (
        <Clock3 size={15} aria-hidden="true" />
      )}
      {running ? "Running..." : "Run date"}
    </button>
  );
}

function ArchiveIconButton({
  children,
  disabled = false,
  label,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-[var(--border-warm)] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)] disabled:cursor-not-allowed disabled:opacity-45"
    >
      {children}
    </button>
  );
}

function ArchiveSignal({
  active = false,
  icon: Icon,
  label,
  value,
}: {
  active?: boolean;
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div
      className={`rounded-lg border px-3 py-2 ${
        active
          ? "border-[rgba(127,155,122,0.35)] bg-[rgba(127,155,122,0.08)]"
          : "border-[var(--border-warm)] bg-[rgba(238,229,216,0.32)]"
      }`}
    >
      <div className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase text-[var(--text-faint)]">
        <Icon size={13} aria-hidden="true" />
        {label}
      </div>
      <div className="font-mono text-xs text-[var(--text-note)]">{value}</div>
    </div>
  );
}

function getArchiveDate(value: string | null, fallback: string): string {
  if (!value || !ISO_DATE_PATTERN.test(value) || value > fallback) {
    return fallback;
  }

  return toIsoDate(dateFromIsoDate(value)) === value ? value : fallback;
}

function getArchiveCategory(value: string | null): ArchiveCategory {
  return ARCHIVE_CATEGORIES.includes(value as ArchiveCategory) ? (value as ArchiveCategory) : "all";
}

function getBackfillRangeError(startDate: string, endDate: string, today: string): string | null {
  if (!isValidIsoDate(startDate) || !isValidIsoDate(endDate)) {
    return "Choose a valid date range.";
  }

  if (startDate > today || endDate > today) {
    return "Backfill range cannot include future dates.";
  }

  if (endDate < startDate) {
    return "End date must be on or after start date.";
  }

  if (countIsoDateDays(startDate, endDate) > MAX_BACKFILL_DAYS) {
    return `Limit range to ${MAX_BACKFILL_DAYS} days.`;
  }

  return null;
}

function isValidIsoDate(value: string): boolean {
  return ISO_DATE_PATTERN.test(value) && toIsoDate(dateFromIsoDate(value)) === value;
}

function countIsoDateDays(startDate: string, endDate: string): number {
  if (!isValidIsoDate(startDate) || !isValidIsoDate(endDate) || endDate < startDate) {
    return 0;
  }

  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  const startTime = dateFromIsoDate(startDate).getTime();
  const endTime = dateFromIsoDate(endDate).getTime();

  return Math.floor((endTime - startTime) / millisecondsPerDay) + 1;
}

function mergeBackfillJobs(preferredJob: BackfillJob | undefined, jobs: BackfillJob[]): BackfillJob[] {
  if (!preferredJob) {
    return jobs;
  }

  return [preferredJob, ...jobs.filter((job) => job.id !== preferredJob.id)];
}

function countCategories(papers: PaperWithBreakdown[]): number {
  return new Set(papers.flatMap((paper) => paper.categories)).size;
}
