export function SkeletonCard() {
  return (
    <article className="rounded-[14px] border border-[var(--border-warm)] bg-[var(--bg-card)] p-6 shadow-card">
      <div className="mb-5 flex items-center justify-between">
        <div className="shimmer h-7 w-24 rounded-full" />
        <div className="shimmer h-4 w-20 rounded" />
      </div>
      <div className="shimmer mb-3 h-4 w-44 rounded" />
      <div className="shimmer mb-3 h-8 w-full rounded" />
      <div className="shimmer mb-6 h-8 w-4/5 rounded" />
      <div className="shimmer h-20 w-full rounded-lg" />
    </article>
  );
}
