import { AlertCircle, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import type { DigestStatus } from "../types/api";
import { formatDigestDate, formatTimeAgo } from "../lib/format";
import { RunDigestButton } from "./RunDigestButton";

type DigestHeaderProps = {
  title?: string;
  headline?: string;
  meta?: string;
  total: number;
  categoryCount: number;
  status?: DigestStatus;
  action?: ReactNode;
};

export function DigestHeader({ title, headline, meta, total, categoryCount, status, action }: DigestHeaderProps) {
  return (
    <section className="sticky top-[86px] z-20 -mx-4 mb-6 border-b border-[rgba(222,211,192,0.75)] bg-[rgba(246,239,230,0.88)] px-4 pb-5 pt-1 backdrop-blur md:top-0 md:-mx-2 md:px-2 md:pt-0">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 font-mono text-xs uppercase text-[var(--text-faint)]">
            <Sparkles size={14} aria-hidden="true" />
            {title ?? "Daily Feed"}
          </div>
          <h1 className="font-serif text-[30px] leading-tight text-[var(--text-ink)] sm:text-4xl">
            {headline ?? formatDigestDate()}
          </h1>
          <p className="mt-1 font-mono text-xs text-[var(--text-faint)]">
            {meta ?? `${total} papers · ${categoryCount} categories · updated ${formatTimeAgo(status?.last_run_at)}`}
          </p>
        </div>
        {action === undefined ? <RunDigestButton /> : action}
      </div>
      {status?.status === "failed" && status.error_message ? (
        <div className="mt-4 flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(255,250,243,0.54)] px-3 py-2 text-sm text-[var(--text-note)]">
          <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
          <span>{status.error_message}</span>
        </div>
      ) : null}
    </section>
  );
}
