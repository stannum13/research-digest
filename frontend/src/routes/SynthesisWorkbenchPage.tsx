import { motion } from "framer-motion";
import {
  AlertCircle,
  Archive,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Network,
  Newspaper,
  Play,
  Trash2,
  X,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { DigestHeader } from "../components/DigestHeader";
import { useSynthesisSelection } from "../context/SynthesisSelectionContext";
import type { SelectedSynthesisPaper } from "../context/SynthesisSelectionContext";
import { useCreateSynthesisRun, useSynthesisRun, useSynthesisRuns } from "../hooks/useDigestApi";
import { formatShortDate, formatTimestamp, sentenceList } from "../lib/format";
import type { SynthesisMode, SynthesisOutput, SynthesisRun, SynthesisRunsResponse, SynthesisRunSummary } from "../types/api";

type SourcePaper = Pick<SelectedSynthesisPaper, "id" | "title" | "arxiv_id">;

const SYNTHESIS_MODES = [
  { value: "compare", label: "Compare" },
  { value: "argument_map", label: "Argument map" },
  { value: "research_plan", label: "Research plan" },
  { value: "overview", label: "Overview" },
] satisfies Array<{ value: SynthesisMode; label: string }>;

const SYNTHESIS_SECTIONS = [
  { key: "argument_map", title: "Argument Map", matrix: false },
  { key: "contradictions", title: "Contradictions", matrix: false },
  { key: "evidence_matrix", title: "Evidence Matrix", matrix: true },
  { key: "open_questions", title: "Open Questions", matrix: false },
  { key: "extension_ideas", title: "Extension Ideas", matrix: false },
  { key: "replication_or_ablation_plan", title: "Replication/Ablation Plan", matrix: false },
  { key: "caveats", title: "Caveats", matrix: false },
] as const;

export function SynthesisWorkbenchPage() {
  const {
    clearSelection,
    limit,
    removePaper,
    selectedCount,
    selectedIds,
    selectedPapers,
  } = useSynthesisSelection();
  const [mode, setMode] = useState<SynthesisMode>(SYNTHESIS_MODES[0].value);
  const [instructions, setInstructions] = useState("");
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const createRun = useCreateSynthesisRun();
  const runsQuery = useSynthesisRuns();
  const activeRunQuery = useSynthesisRun(activeRunId);
  const selectedById = useMemo(
    () => new Map(selectedPapers.map((paper) => [paper.id, paper])),
    [selectedPapers],
  );
  const categoryCount = useMemo(
    () => new Set(selectedPapers.flatMap((paper) => paper.categories)).size,
    [selectedPapers],
  );
  const runs = useMemo(() => getRunsFromResponse(runsQuery.data), [runsQuery.data]);
  const activeRun =
    activeRunQuery.data ?? (activeRunId === createRun.data?.id ? createRun.data : undefined);
  const canGenerate = selectedCount >= 2 && !createRun.isPending;

  function requestSynthesis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canGenerate) {
      return;
    }

    const trimmedInstructions = instructions.trim();
    createRun.mutate(
      {
        paper_ids: selectedIds,
        mode,
        instructions: trimmedInstructions || undefined,
      },
      {
        onSuccess: (run) => setActiveRunId(run.id),
      },
    );
  }

  return (
    <>
      <DigestHeader
        title="Synthesis"
        headline="Workbench"
        total={selectedCount}
        categoryCount={categoryCount}
        meta={`${selectedCount}/${limit} selected · ${categoryCount} categories`}
        action={<SynthesisHeaderActions limit={limit} selectedCount={selectedCount} onClear={clearSelection} />}
      />

      <section className="mb-6 rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.72)] p-4 shadow-card sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-warm)] pb-4">
          <div>
            <h2 className="font-serif text-2xl text-[var(--text-ink)]">Selected Papers</h2>
            <p className="font-mono text-[11px] text-[var(--text-faint)]">
              {selectedCount} of {limit}
            </p>
          </div>
          <Link
            to="/"
            className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--border-warm)] px-3.5 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
          >
            Feed
            <ExternalLink size={13} aria-hidden="true" />
          </Link>
        </div>

        {selectedPapers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border-strong)] bg-[rgba(238,229,216,0.34)] px-4 py-8 text-center">
            <Network className="mx-auto mb-3 text-[var(--text-faint)]" size={28} aria-hidden="true" />
            <h3 className="font-serif text-2xl text-[var(--text-ink)]">No papers selected.</h3>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link
                to="/"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--accent-clay)] px-3.5 py-2 font-mono text-[11px] text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
              >
                <Newspaper size={14} aria-hidden="true" />
                Feed
              </Link>
              <Link
                to="/archive"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--border-warm)] px-3.5 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
              >
                <Archive size={14} aria-hidden="true" />
                Archive
              </Link>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-warm)] border-y border-[var(--border-warm)]">
            {selectedPapers.map((paper) => (
              <SelectedPaperRow key={paper.id} paper={paper} onRemove={() => removePaper(paper.id)} />
            ))}
          </div>
        )}

        <form onSubmit={requestSynthesis} className="mt-5 space-y-4 border-t border-[var(--border-warm)] pt-4">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]">
            <label className="grid gap-2">
              <span className="font-mono text-[11px] uppercase text-[var(--text-faint)]">Mode</span>
              <select
                aria-label="Synthesis mode"
                value={mode}
                onChange={(event) => setMode(event.currentTarget.value as SynthesisMode)}
                className="min-h-11 rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 font-mono text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              >
                {SYNTHESIS_MODES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid gap-2">
              <span className="font-mono text-[11px] uppercase text-[var(--text-faint)]">Instructions</span>
              <textarea
                aria-label="Synthesis instructions"
                value={instructions}
                onChange={(event) => setInstructions(event.currentTarget.value)}
                rows={3}
                className="min-h-24 resize-y rounded-lg border border-[var(--border-warm)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-ink)] outline-none transition focus:border-[var(--accent-clay)]"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div aria-live="polite" className="font-mono text-[11px] text-[var(--text-faint)]">
              {selectedCount < 2 ? "Need 2 papers." : `${selectedCount} papers ready.`}
            </div>
            <button
              type="submit"
              disabled={!canGenerate}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)] disabled:cursor-not-allowed disabled:border-[var(--border-warm)] disabled:text-[var(--text-faint)] disabled:hover:bg-transparent"
            >
              {createRun.isPending ? (
                <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
                  <Loader2 size={15} aria-hidden="true" />
                </motion.span>
              ) : (
                <Play size={14} aria-hidden="true" />
              )}
              {createRun.isPending ? "Generating..." : "Generate synthesis"}
            </button>
          </div>

          {createRun.isError ? (
            <div className="flex gap-2 rounded-lg border border-[rgba(199,131,127,0.35)] bg-[rgba(255,250,243,0.54)] px-3 py-2 text-sm text-[var(--text-note)]">
              <AlertCircle className="mt-0.5 shrink-0 text-[var(--accent-rose)]" size={16} aria-hidden="true" />
              <span>Synthesis request failed.</span>
            </div>
          ) : null}
        </form>
      </section>

      {runs.length > 0 || runsQuery.isError ? (
        <SynthesisRunHistory
          activeRunId={activeRunId}
          error={runsQuery.isError}
          runs={runs}
          onSelect={setActiveRunId}
        />
      ) : null}

      <SynthesisResultPanel
        loading={activeRunQuery.isFetching && Boolean(activeRunId)}
        run={activeRun}
        selectedById={selectedById}
      />
    </>
  );
}

function SynthesisHeaderActions({
  limit,
  onClear,
  selectedCount,
}: {
  limit: number;
  onClear: () => void;
  selectedCount: number;
}) {
  const ready = selectedCount >= 2;

  return (
    <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-2 sm:w-auto sm:grid-cols-[9.75rem_auto]">
      <div
        aria-live="polite"
        className="inline-flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-full border border-[var(--border-warm)] bg-[rgba(255,250,243,0.68)] px-3.5 py-2 font-mono text-xs text-[var(--text-note)]"
      >
        <span className="inline-flex min-w-0 items-center gap-2">
          <Network className="shrink-0 text-[var(--accent-sage)]" size={14} aria-hidden="true" />
          <span className="tabular-nums">
            {selectedCount}/{limit}
          </span>
        </span>
        <span className={ready ? "text-[var(--accent-sage)]" : "text-[var(--text-faint)]"}>
          {ready ? "Ready" : "Need 2"}
        </span>
      </div>
      <button
        type="button"
        onClick={onClear}
        disabled={selectedCount === 0}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[var(--border-warm)] px-4 py-2 font-mono text-xs text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-[var(--border-warm)] disabled:hover:text-[var(--text-note)]"
      >
        <Trash2 size={14} aria-hidden="true" />
        Clear
      </button>
    </div>
  );
}

function SelectedPaperRow({
  onRemove,
  paper,
}: {
  onRemove: () => void;
  paper: SelectedSynthesisPaper;
}) {
  return (
    <article className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div>
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[rgba(127,155,122,0.12)] px-2.5 py-1 font-mono text-[10px] uppercase text-[var(--accent-sage)]">
            {paper.primary_category}
          </span>
          {paper.score !== null ? (
            <span className="rounded-full bg-[rgba(238,229,216,0.72)] px-2.5 py-1 font-mono text-[10px] uppercase text-[var(--text-note)]">
              Score {paper.score.toFixed(1)}
            </span>
          ) : null}
          <span className="font-mono text-[11px] text-[var(--text-faint)]">
            {formatShortDate(paper.published_at)} · {paper.arxiv_id}
          </span>
        </div>
        <h3 className="[overflow-wrap:anywhere] font-serif text-xl leading-snug text-[var(--text-ink)]">
          {paper.title}
        </h3>
        <p className="mt-1 font-mono text-[11px] text-[var(--text-faint)]">{sentenceList(paper.authors, 4)}</p>
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${paper.title} from synthesis selection`}
        className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-warm)] text-[var(--text-note)] transition hover:border-[var(--accent-rose)] hover:text-[var(--accent-rose)]"
      >
        <X size={16} aria-hidden="true" />
      </button>
    </article>
  );
}

function SynthesisRunHistory({
  activeRunId,
  error,
  onSelect,
  runs,
}: {
  activeRunId: number | null;
  error: boolean;
  onSelect: (runId: number) => void;
  runs: SynthesisRunSummary[];
}) {
  if (error && runs.length === 0) {
    return (
      <section className="mb-6 rounded-[14px] border border-[rgba(199,131,127,0.35)] bg-[rgba(255,250,243,0.58)] p-4 text-sm text-[var(--text-note)]">
        Recent synthesis runs unavailable.
      </section>
    );
  }

  return (
    <section className="mb-6 rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.58)] p-4 shadow-card">
      <div className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase text-[var(--text-faint)]">
        <Network size={14} aria-hidden="true" />
        Recent Runs
      </div>
      <div className="scrollbar-soft -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {runs.slice(0, 8).map((run) => (
          <button
            key={run.id}
            type="button"
            onClick={() => onSelect(run.id)}
            className={`shrink-0 rounded-full border px-3.5 py-2 font-mono text-[11px] transition ${
              activeRunId === run.id
                ? "border-[var(--accent-clay)] bg-[var(--accent-clay)] text-[var(--bg-card)]"
                : "border-[var(--border-warm)] bg-[rgba(255,250,243,0.58)] text-[var(--text-note)] hover:border-[var(--accent-clay)]"
            }`}
          >
            Run #{run.id} · {run.mode}
          </button>
        ))}
      </div>
    </section>
  );
}

function SynthesisResultPanel({
  loading,
  run,
  selectedById,
}: {
  loading: boolean;
  run?: SynthesisRun;
  selectedById: Map<number, SelectedSynthesisPaper>;
}) {
  if (loading && !run) {
    return (
      <section className="rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.72)] p-5 text-[var(--text-note)] shadow-card">
        <span className="inline-flex items-center gap-2 font-mono text-xs">
          <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}>
            <Loader2 size={15} aria-hidden="true" />
          </motion.span>
          Loading synthesis...
        </span>
      </section>
    );
  }

  if (!run) {
    return null;
  }

  const output = getSynthesisOutput(run);
  const sourceIds = getSourcePaperIds(output, run.selected_papers);
  const sourcePaperById = getSourcePaperById(run, selectedById);

  return (
    <section
      aria-live="polite"
      className="rounded-[14px] border border-[var(--border-warm)] bg-[rgba(255,250,243,0.78)] p-5 shadow-card"
    >
      <div className="mb-5 flex flex-col gap-3 border-b border-[var(--border-warm)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h2 className="font-serif text-2xl text-[var(--text-ink)]">Run #{run.id}</h2>
            <span className="rounded-full bg-[rgba(127,155,122,0.12)] px-2.5 py-1 font-mono text-[10px] uppercase text-[var(--accent-sage)]">
              Stored
            </span>
          </div>
          <p className="font-mono text-[11px] text-[var(--text-faint)]">
            {run.mode} · {formatTimestamp(output.created_at ?? run.created_at)}
          </p>
        </div>
        <div className="font-mono text-[11px] text-[var(--text-faint)]">
          {output.model_provider || run.model_provider ? `${output.model_provider ?? run.model_provider} · ` : null}
          {output.model_name ?? run.model_name ?? "model pending"}
          {output.prompt_version ?? run.prompt_version ? ` · ${output.prompt_version ?? run.prompt_version}` : null}
        </div>
      </div>

      <div className="space-y-5">
        {SYNTHESIS_SECTIONS.map((section) => (
          <SynthesisSection
            key={section.key}
            matrix={section.matrix}
            title={section.title}
            value={output[section.key]}
          />
        ))}
        <SourceSection sourceIds={sourceIds} sourcePaperById={sourcePaperById} />
      </div>
    </section>
  );
}

function SynthesisSection({
  matrix = false,
  title,
  value,
}: {
  matrix?: boolean;
  title: string;
  value: unknown;
}) {
  return (
    <section className="border-t border-[var(--border-warm)] pt-4 first:border-t-0 first:pt-0">
      <SectionLabel title={title} />
      <div className="mt-3">{renderSynthesisValue(value, matrix)}</div>
    </section>
  );
}

function SourceSection({
  sourcePaperById,
  sourceIds,
}: {
  sourcePaperById: ReadonlyMap<number, SourcePaper>;
  sourceIds: number[];
}) {
  return (
    <section className="border-t border-[var(--border-warm)] pt-4">
      <SectionLabel title="Sources" />
      {sourceIds.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--text-faint)]">No source papers returned.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {sourceIds.map((paperId) => {
            const paper = sourcePaperById.get(paperId);
            return (
              <li key={paperId} className="flex gap-2 text-sm leading-6 text-[var(--text-note)]">
                <CheckCircle2 className="mt-1 shrink-0 text-[var(--accent-sage)]" size={14} aria-hidden="true" />
                <span>
                  {paper ? paper.title : `Paper #${paperId}`}
                  {paper ? <span className="text-[var(--text-faint)]"> · {paper.arxiv_id}</span> : null}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function SectionLabel({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3">
      <h3 className="shrink-0 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--text-faint)]">{title}</h3>
      <div className="h-px flex-1 bg-[var(--border-warm)]" />
    </div>
  );
}

function renderSynthesisValue(value: unknown, matrix: boolean): ReactNode {
  if (isEmptyValue(value)) {
    return <p className="text-sm text-[var(--text-faint)]">No entries returned.</p>;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <p className="leading-7 text-[var(--text-note)]">{String(value)}</p>;
  }

  if (Array.isArray(value)) {
    const records = value.filter(isRecord);

    if (matrix && records.length === value.length && records.length > 0) {
      return <SynthesisTable rows={records} />;
    }

    return (
      <ul className="space-y-3">
        {value.map((item, index) => (
          <li key={index} className="flex gap-3 leading-7 text-[var(--text-note)]">
            <span className="mt-0.5 font-mono text-lg leading-7 text-[var(--accent-clay)]">•</span>
            <span>{renderNestedValue(item)}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (isRecord(value)) {
    return <ObjectValue value={value} />;
  }

  return <p className="leading-7 text-[var(--text-note)]">{String(value)}</p>;
}

function ObjectValue({ value }: { value: Record<string, unknown> }) {
  return (
    <div className="grid gap-3">
      {Object.entries(value).map(([key, item]) => (
        <div key={key} className="grid gap-1 border-l-2 border-[var(--border-warm)] pl-3">
          <dt className="font-mono text-[11px] uppercase text-[var(--text-faint)]">{formatSynthesisLabel(key)}</dt>
          <dd className="leading-7 text-[var(--text-note)]">{renderNestedValue(item)}</dd>
        </div>
      ))}
    </div>
  );
}

function SynthesisTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));

  return (
    <div className="scrollbar-soft overflow-x-auto rounded-lg border border-[var(--border-warm)]">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-[rgba(238,229,216,0.62)] font-mono text-[10px] uppercase text-[var(--text-faint)]">
          <tr>
            {columns.map((column) => (
              <th key={column} className="border-b border-[var(--border-warm)] px-3 py-2 font-medium">
                {formatSynthesisLabel(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-warm)]">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column} className="min-w-40 px-3 py-3 align-top text-[var(--text-note)]">
                  {renderNestedValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderNestedValue(value: unknown): ReactNode {
  if (isEmptyValue(value)) {
    return <span className="text-[var(--text-faint)]">none</span>;
  }

  if (Array.isArray(value)) {
    return value.map((item) => formatCellValue(item)).join(", ");
  }

  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, item]) => `${formatSynthesisLabel(key)}: ${formatCellValue(item)}`)
      .join("; ");
  }

  return String(value);
}

function formatCellValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(formatCellValue).join(", ");
  }

  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, item]) => `${formatSynthesisLabel(key)}: ${formatCellValue(item)}`)
      .join("; ");
  }

  return value === null || value === undefined ? "none" : String(value);
}

function getSynthesisOutput(run: SynthesisRun): Partial<SynthesisOutput> {
  return {
    argument_map: run.argument_map,
    contradictions: run.contradictions,
    evidence_matrix: run.evidence_matrix,
    open_questions: run.open_questions,
    extension_ideas: run.extension_ideas,
    replication_or_ablation_plan: run.replication_or_ablation_plan,
    caveats: run.caveats,
    source_paper_ids: run.source_paper_ids,
    prompt_version: run.prompt_version,
    model_provider: run.model_provider,
    model_name: run.model_name,
    created_at: run.created_at,
  };
}

function getSourcePaperIds(output: Partial<SynthesisOutput>, selectedPapers: SourcePaper[]): number[] {
  if (Array.isArray(output.source_paper_ids) && output.source_paper_ids.length > 0) {
    return output.source_paper_ids;
  }

  return selectedPapers.map((paper) => paper.id);
}

function getSourcePaperById(
  run: SynthesisRun,
  selectedById: ReadonlyMap<number, SourcePaper>,
): Map<number, SourcePaper> {
  const sourcePaperById = new Map<number, SourcePaper>();

  for (const paper of run.selected_papers) {
    sourcePaperById.set(paper.id, paper);
  }

  for (const paperId of run.source_paper_ids) {
    const selectedPaper = selectedById.get(paperId);

    if (selectedPaper && !sourcePaperById.has(paperId)) {
      sourcePaperById.set(paperId, selectedPaper);
    }
  }

  return sourcePaperById;
}

function getRunsFromResponse(response: SynthesisRunsResponse | undefined): SynthesisRunSummary[] {
  return response?.items ?? [];
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") {
    return true;
  }

  if (Array.isArray(value)) {
    return value.length === 0;
  }

  if (isRecord(value)) {
    return Object.keys(value).length === 0;
  }

  return false;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatSynthesisLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
