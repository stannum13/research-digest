import { Loader2, Play } from "lucide-react";
import { motion } from "framer-motion";

import { useRunDigest } from "../hooks/useDigestApi";

export function RunDigestButton() {
  const runDigest = useRunDigest();
  const running = runDigest.isPending;

  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <button
        type="button"
        onClick={() => runDigest.mutate(undefined)}
        disabled={running}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-wait disabled:opacity-70"
      >
        {running ? (
          <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
            <Loader2 size={15} aria-hidden="true" />
          </motion.span>
        ) : (
          <Play size={14} aria-hidden="true" />
        )}
        {running ? "Running..." : "Run digest"}
      </button>
      {runDigest.data ? (
        <p className="max-w-[18rem] text-left font-mono text-[11px] text-[var(--text-faint)] sm:text-right">
          Run #{runDigest.data.id}: {runDigest.data.status} · {runDigest.data.papers_summarized}/
          {runDigest.data.papers_fetched} summarized
        </p>
      ) : null}
      {runDigest.isError ? (
        <p className="max-w-[18rem] text-left font-mono text-[11px] text-[var(--accent-rose)] sm:text-right">
          Run request failed.
        </p>
      ) : null}
    </div>
  );
}
