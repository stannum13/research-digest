import { AlertCircle, CheckCircle2, Clock, Loader2, Play, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";

import { useRunBackfillJob } from "../hooks/useDigestApi";
import { formatTimestamp } from "../lib/format";
import type { BackfillJob } from "../types/api";

type BackfillJobListProps = {
  className?: string;
  emptyMessage?: string;
  jobs: BackfillJob[];
  limit?: number;
};

export function BackfillJobList({
  className = "",
  emptyMessage = "No backfill jobs yet.",
  jobs,
  limit = 3,
}: BackfillJobListProps) {
  const runBackfillJob = useRunBackfillJob();
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [runError, setRunError] = useState<{ jobId: number; message: string } | null>(null);
  const recentJobs = jobs.slice(0, limit);

  function runJob(job: BackfillJob) {
    setActiveJobId(job.id);
    setRunError(null);
    runBackfillJob.mutate(job.id, {
      onError: (error) => {
        setRunError({ jobId: job.id, message: error.message || "Run request failed." });
      },
      onSettled: () => {
        setActiveJobId(null);
      },
    });
  }

  if (!recentJobs.length) {
    return (
      <p className={`rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.38)] p-3 text-sm text-[var(--text-note)] ${className}`}>
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className={`divide-y divide-[var(--border-warm)] ${className}`}>
      {recentJobs.map((job) => {
        const canRun = job.status === "pending" || job.status === "failed";
        const runningThisJob = runBackfillJob.isPending && activeJobId === job.id;
        const actionLabel = job.status === "failed" ? "Resume" : "Run";
        const dateRange = job.start_date === job.end_date ? job.start_date : `${job.start_date} to ${job.end_date}`;
        const categoryScope = job.category_scope.length ? job.category_scope.join(", ") : "all categories";

        return (
          <div key={job.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-[var(--text-note)]">
                  Job #{job.id} · {dateRange}
                </span>
                <BackfillStatusBadge status={job.status} />
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-[var(--text-faint)]">
                <span>{formatTimestamp(job.completed_at ?? job.started_at ?? job.created_at)}</span>
                <span>{categoryScope}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-[var(--text-note)]">
                <span>{formatJobProgress(job)}</span>
                <span>{formatJobBudget(job)}</span>
              </div>
              {job.error_message ? (
                <div className="mt-2 flex gap-1.5 text-xs text-[var(--accent-rose)]">
                  <AlertCircle className="mt-0.5 shrink-0" size={13} aria-hidden="true" />
                  {job.error_message}
                </div>
              ) : null}
              {runError?.jobId === job.id ? (
                <div
                  role="alert"
                  className="mt-2 flex gap-1.5 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(199,131,127,0.08)] p-2 text-xs text-[var(--text-note)]"
                >
                  <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={13} aria-hidden="true" />
                  Run failed: {runError.message}
                </div>
              ) : null}
            </div>
            {canRun ? (
              <button
                type="button"
                aria-label={`${actionLabel} backfill job #${job.id}`}
                disabled={runBackfillJob.isPending}
                onClick={() => runJob(job)}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-3.5 py-2 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-wait disabled:opacity-70"
              >
                {runningThisJob ? (
                  <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                ) : job.status === "failed" ? (
                  <RotateCcw size={14} aria-hidden="true" />
                ) : (
                  <Play size={14} aria-hidden="true" />
                )}
                {runningThisJob ? "Running..." : actionLabel}
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function formatJobProgress(job: BackfillJob): string {
  return `${job.completed_days}/${job.total_days} days · ${job.failed_days} failed · ${job.papers_summarized}/${job.papers_fetched} summarized`;
}

function formatJobBudget(job: BackfillJob): string {
  return `$${job.budget_remaining_usd.toFixed(2)} of $${job.budget_usd.toFixed(2)} remaining · $${job.estimated_cost_usd.toFixed(2)} estimated`;
}

function BackfillStatusBadge({ status }: { status: BackfillJob["status"] }) {
  const failed = status === "failed";
  const running = status === "running" || status === "pending";
  const canceled = status === "canceled";
  const Icon = failed ? AlertCircle : canceled ? XCircle : running ? Clock : CheckCircle2;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase ${
        failed
          ? "bg-[rgba(199,131,127,0.12)] text-[var(--accent-rose)]"
          : running
            ? "bg-[rgba(196,162,79,0.14)] text-[#8b6b3d]"
            : canceled
              ? "bg-[rgba(238,229,216,0.62)] text-[var(--text-faint)]"
              : "bg-[rgba(127,155,122,0.12)] text-[var(--accent-sage)]"
      }`}
    >
      <Icon size={12} aria-hidden="true" />
      {status}
    </span>
  );
}
