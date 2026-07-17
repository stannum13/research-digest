import { motion } from "framer-motion";

import { filterOptions, type FilterId } from "../lib/tags";

type FilterBarProps = {
  selected: FilterId;
  onSelect: (filter: FilterId) => void;
};

export function FilterBar({ selected, onSelect }: FilterBarProps) {
  return (
    <div className="scrollbar-soft -mx-4 mb-6 flex gap-2 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0">
      {filterOptions.map((filter) => {
        const active = selected === filter.id;
        return (
          <button
            key={filter.id}
            type="button"
            className={`relative shrink-0 overflow-hidden rounded-full border px-3.5 py-2 font-mono text-[11px] transition ${
              active
                ? "border-[var(--accent-clay)] text-[var(--bg-card)]"
                : "border-[var(--border-warm)] bg-[rgba(255,250,243,0.58)] text-[var(--text-note)] hover:border-[var(--accent-clay)]"
            }`}
            onClick={() => onSelect(filter.id)}
          >
            {active ? <motion.span layoutId="filterChip" className="absolute inset-0 bg-[var(--accent-clay)]" /> : null}
            <span className="relative">{filter.label}</span>
          </button>
        );
      })}
    </div>
  );
}
