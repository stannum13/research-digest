type ErrorStateProps = {
  onRetry?: () => void;
};

export function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <div className="rounded-[14px] border border-[rgba(199,131,127,0.45)] bg-[rgba(255,250,243,0.72)] p-6 text-[var(--text-note)] shadow-card">
      <h2 className="mb-2 font-serif text-2xl text-[var(--text-ink)]">The feed ran into trouble.</h2>
      {onRetry ? (
        <button
          className="mt-3 rounded-full border border-[var(--accent-clay)] px-4 py-2 font-mono text-xs text-[var(--accent-clay)] transition hover:bg-[var(--accent-clay)] hover:text-[var(--bg-card)]"
          type="button"
          onClick={onRetry}
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
