import { AnimatePresence, motion } from "framer-motion";
import {
  Bookmark,
  BookmarkCheck,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  ExternalLink,
  Plus,
  WandSparkles,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useSynthesisSelection } from "../context/SynthesisSelectionContext";
import { useClassifyPaper, usePaperClassifications, useToggleSave } from "../hooks/useDigestApi";
import { formatShortDate, sentenceList } from "../lib/format";
import { notebookEase, staggerTransition } from "../lib/motion";
import { useReducedMotionSafe } from "../hooks/useReducedMotionSafe";
import type { PaperClassification, PaperWithBreakdown } from "../types/api";
import { FeedbackBar } from "./FeedbackBar";
import { TagChip } from "./TagChip";

type PaperCardProps = {
  paper: PaperWithBreakdown;
  index: number;
};

export function PaperCard({ paper, index }: PaperCardProps) {
  const [expanded, setExpanded] = useState(false);
  const reducedMotion = useReducedMotionSafe();
  const toggleSave = useToggleSave();
  const { canSelectPaper, isSelected, limit, togglePaper } = useSynthesisSelection();
  const breakdown = paper.breakdown;
  const classificationsQuery = usePaperClassifications(paper.arxiv_id, expanded && Boolean(breakdown));
  const classifyPaper = useClassifyPaper(paper.arxiv_id);
  const difficulty = breakdown?.difficulty ?? "intermediate";
  const selectedForSynthesis = isSelected(paper.id);
  const selectionDisabled = !selectedForSynthesis && !canSelectPaper(paper.id);

  return (
    <motion.article
      layout
      initial={reducedMotion ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      whileHover={reducedMotion ? undefined : { y: -3 }}
      transition={staggerTransition(index, reducedMotion)}
      className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-5 shadow-card transition-colors hover:border-[rgba(183,119,85,0.5)] sm:p-6"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-warm)] pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <TagChip tone="category" category={paper.primary_category}>
            {paper.primary_category}
          </TagChip>
          {breakdown ? (
            <TagChip tone="difficulty" difficulty={difficulty}>
              {difficulty}
            </TagChip>
          ) : null}
          <PaperStatusChip summarized={Boolean(breakdown)} />
          <PaperScore score={paper.score} />
        </div>
        <div className="font-mono text-[11px] text-[var(--text-faint)]">
          {formatShortDate(paper.published_at)} · {paper.arxiv_id}
        </div>
      </div>

      {breakdown?.vibe ? <p className="mb-3 font-serif text-base italic text-[var(--text-faint)]">{breakdown.vibe}</p> : null}
      <h2 className="mb-3 [overflow-wrap:anywhere] font-serif text-[26px] font-medium leading-[1.25] text-[var(--text-ink)]">
        {paper.title}
      </h2>
      <p className="mb-4 font-mono text-[11px] leading-relaxed text-[var(--text-faint)]">
        {sentenceList(paper.authors, 4)} · updated {formatShortDate(paper.updated_at)}
      </p>

      <p className="border-y border-[var(--border-warm)] py-4 text-[16px] italic leading-7 text-[var(--text-note)]">
        {breakdown?.one_line_takeaway ?? paper.abstract}
      </p>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {(breakdown?.tags ?? paper.categories).slice(0, 4).map((tag) => (
            <TagChip key={tag}>{tag}</TagChip>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`inline-flex h-10 w-10 items-center justify-center rounded-full border transition ${
              selectedForSynthesis
                ? "border-[var(--accent-sage)] bg-[rgba(127,155,122,0.12)] text-[var(--accent-sage)]"
                : "border-[var(--border-warm)] text-[var(--text-note)] hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
            } disabled:cursor-not-allowed disabled:opacity-45`}
            aria-label={
              selectedForSynthesis
                ? "Remove paper from synthesis selection"
                : selectionDisabled
                  ? `Selection limit reached (${limit})`
                  : "Add paper to synthesis selection"
            }
            aria-pressed={selectedForSynthesis}
            disabled={selectionDisabled}
            title={selectionDisabled ? `Selection limit reached (${limit})` : undefined}
            onClick={() => togglePaper(paper)}
          >
            {selectedForSynthesis ? <Check size={17} aria-hidden="true" /> : <Plus size={17} aria-hidden="true" />}
          </button>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-warm)] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
            aria-label={paper.is_saved ? "Remove bookmark" : "Bookmark paper"}
            onClick={() => toggleSave.mutate(paper.arxiv_id)}
          >
            <motion.span
              animate={
                paper.is_saved && !reducedMotion
                  ? { scale: [1, 1.3, 1], color: "var(--accent-ochre)" }
                  : { scale: 1, color: paper.is_saved ? "var(--accent-ochre)" : "var(--text-note)" }
              }
              transition={{ duration: 0.3 }}
            >
              {paper.is_saved ? <BookmarkCheck size={17} aria-hidden="true" /> : <Bookmark size={17} aria-hidden="true" />}
            </motion.span>
          </button>
          <a
            href={paper.arxiv_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-warm)] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
            aria-label="Open paper on arXiv"
          >
            <ExternalLink size={16} aria-hidden="true" />
          </a>
          <button
            type="button"
            className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--border-warm)] px-3.5 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)] disabled:cursor-not-allowed disabled:opacity-55"
            onClick={() => setExpanded((value) => !value)}
            disabled={!breakdown}
            aria-expanded={expanded}
          >
            {breakdown ? (expanded ? "Close" : "Expand") : "Pending"}
            {breakdown ? (
              <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={15} aria-hidden="true" />
              </motion.span>
            ) : (
              <Clock3 size={15} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {expanded && breakdown ? (
          <motion.div
            key="expanded"
            initial={reducedMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: notebookEase }}
            className="overflow-hidden"
          >
            <div className="mt-6 space-y-6 border-t border-[var(--border-warm)] pt-5">
              <ExpandedSection title="Context">{breakdown.context}</ExpandedSection>
              <ExpandedSection title="What's New">{breakdown.what_is_new}</ExpandedSection>
              <ExpandedSection title="Mechanism">{breakdown.mechanism}</ExpandedSection>
              <ExpandedSection title="Evidence">{breakdown.evidence}</ExpandedSection>

              <ExpandedList title="Caveats" items={breakdown.methodology_caveats} tone="rose" />
              <ExpandedList title="Possible Extensions" items={breakdown.meaningful_extensions} tone="sage" />

              <div className="rounded-lg border border-[var(--border-warm)] bg-[rgba(238,229,216,0.5)] p-4">
                <p className="mb-2 text-sm text-[var(--text-note)]">
                  <span className="font-mono text-[11px] uppercase text-[var(--text-faint)]">Read this if: </span>
                  {breakdown.read_this_if}
                </p>
                <p className="font-mono text-[11px] text-[var(--text-faint)]">
                  Confidence: {breakdown.confidence} · {breakdown.source_basis.split("_").join(" ")}
                </p>
              </div>

              {breakdown.glossary.length ? (
                <div>
                  <SectionLabel title="Glossary" />
                  <div className="mt-3 grid gap-3">
                    {breakdown.glossary.map((item) => (
                      <div key={item.term} className="text-sm text-[var(--text-note)]">
                        <span className="font-semibold text-[var(--text-ink)]">{item.term}: </span>
                        {item.definition}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <ClassificationSection
                classifications={classificationsQuery.data?.items ?? []}
                isLoading={classificationsQuery.isLoading}
                isFetchError={classificationsQuery.isError}
                isClassifying={classifyPaper.isPending}
                isClassifyError={classifyPaper.isError}
                onClassify={() => classifyPaper.mutate()}
              />

              <FeedbackBar arxivId={paper.arxiv_id} />

              <div className="flex flex-wrap gap-2">
                <a
                  href={paper.arxiv_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
                >
                  Open on arXiv
                  <ExternalLink size={14} aria-hidden="true" />
                </a>
                <button
                  type="button"
                  onClick={() => setExpanded(false)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--border-warm)] px-4 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
                >
                  Close
                  <X size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.article>
  );
}

function PaperStatusChip({ summarized }: { summarized: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[10px] uppercase ${
        summarized
          ? "bg-[rgba(127,155,122,0.12)] text-[var(--accent-sage)]"
          : "bg-[rgba(196,162,79,0.14)] text-[#8b6b3d]"
      }`}
    >
      {summarized ? <CheckCircle2 size={12} aria-hidden="true" /> : <Clock3 size={12} aria-hidden="true" />}
      {summarized ? "Summarized" : "Pending"}
    </span>
  );
}

function PaperScore({ score }: { score: number | null }) {
  if (score === null) {
    return null;
  }

  return (
    <span className="rounded-full bg-[rgba(238,229,216,0.72)] px-2.5 py-1 font-mono text-[10px] uppercase text-[var(--text-note)]">
      Score {score.toFixed(1)}
    </span>
  );
}

function ClassificationSection({
  classifications,
  isLoading,
  isFetchError,
  isClassifying,
  isClassifyError,
  onClassify,
}: {
  classifications: PaperClassification[];
  isLoading: boolean;
  isFetchError: boolean;
  isClassifying: boolean;
  isClassifyError: boolean;
  onClassify: () => void;
}) {
  const groups = useMemo(() => groupClassifications(classifications), [classifications]);
  const hasLabels = classifications.length > 0;
  const showAction = !hasLabels && !isLoading;
  const statusText = getClassificationStatus({
    hasLabels,
    isClassifying,
    isClassifyError,
    isFetchError,
    isLoading,
  });

  return (
    <section>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="shrink-0 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--text-faint)]">
          Classifications
        </h3>
        <div className="h-px min-w-12 flex-1 bg-[var(--border-warm)]" />
        {showAction ? (
          <button
            type="button"
            className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-[var(--border-warm)] px-3 py-1.5 font-mono text-[10px] uppercase text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)] disabled:cursor-not-allowed disabled:opacity-55"
            onClick={onClassify}
            disabled={isClassifying}
          >
            <WandSparkles size={13} aria-hidden="true" />
            {isClassifying ? "Extracting" : "Extract labels"}
          </button>
        ) : null}
      </div>

      {statusText ? (
        <p className="mt-3 font-mono text-[11px] text-[var(--text-faint)]">{statusText}</p>
      ) : null}

      {hasLabels ? (
        <div className="mt-3 grid gap-3">
          {groups.map((group) => (
            <div key={group.labelType} className="grid gap-2 sm:grid-cols-[8rem_1fr]">
              <div className="pt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-faint)]">
                {formatLabelType(group.labelType)}
              </div>
              <div className="flex flex-wrap gap-2">
                {group.items.map((item) => (
                  <ClassificationChip key={item.id} classification={item} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ClassificationChip({ classification }: { classification: PaperClassification }) {
  const confidence = formatConfidence(classification.confidence);
  const title = [
    classification.source ? `Source: ${classification.source}` : null,
    confidence ? `Confidence: ${confidence}` : null,
    classification.rationale ? `Rationale: ${classification.rationale}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <span
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[rgba(127,155,122,0.24)] bg-[rgba(127,155,122,0.09)] px-2.5 py-1 text-xs text-[var(--text-note)]"
      title={title || undefined}
    >
      <span className="[overflow-wrap:anywhere]">{classification.label}</span>
      {confidence ? (
        <span className="font-mono text-[10px] text-[var(--text-faint)]">{confidence}</span>
      ) : null}
    </span>
  );
}

function groupClassifications(classifications: PaperClassification[]) {
  const groups = new Map<string, PaperClassification[]>();

  classifications.forEach((classification) => {
    const labelType = classification.label_type || "other";
    const items = groups.get(labelType);

    if (items) {
      items.push(classification);
      return;
    }

    groups.set(labelType, [classification]);
  });

  return Array.from(groups, ([labelType, items]) => ({ labelType, items }));
}

function getClassificationStatus({
  hasLabels,
  isClassifying,
  isClassifyError,
  isFetchError,
  isLoading,
}: {
  hasLabels: boolean;
  isClassifying: boolean;
  isClassifyError: boolean;
  isFetchError: boolean;
  isLoading: boolean;
}) {
  if (hasLabels) {
    return null;
  }

  if (isClassifying) {
    return "Extracting labels...";
  }

  if (isLoading) {
    return "Checking labels...";
  }

  if (isClassifyError) {
    return "Extraction failed.";
  }

  if (isFetchError) {
    return "Labels unavailable.";
  }

  return "No labels yet.";
}

function formatLabelType(labelType: string) {
  return labelType
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatConfidence(confidence: number | null) {
  if (typeof confidence !== "number" || Number.isNaN(confidence)) {
    return null;
  }

  if (confidence >= 0 && confidence <= 1) {
    return `${Math.round(confidence * 100)}%`;
  }

  if (confidence >= 0 && confidence <= 100) {
    return `${Math.round(confidence)}%`;
  }

  return confidence.toFixed(1);
}

function SectionLabel({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3">
      <h3 className="shrink-0 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--text-faint)]">{title}</h3>
      <div className="h-px flex-1 bg-[var(--border-warm)]" />
    </div>
  );
}

function ExpandedSection({ title, children }: { title: string; children: string }) {
  return (
    <section>
      <SectionLabel title={title} />
      <p className="mt-3 leading-7 text-[var(--text-note)]">{children}</p>
    </section>
  );
}

function ExpandedList({ title, items, tone }: { title: string; items: string[]; tone: "rose" | "sage" }) {
  const marker = tone === "rose" ? "var(--accent-rose)" : "var(--accent-sage)";
  return (
    <section>
      <SectionLabel title={title} />
      <ul className="mt-3 space-y-3">
        {items.map((item) => (
          <li key={item} className="flex gap-3 leading-7 text-[var(--text-note)]">
            <span className="mt-0.5 font-mono text-lg leading-7" style={{ color: marker }}>
              {tone === "rose" ? "•" : "→"}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
