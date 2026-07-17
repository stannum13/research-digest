import type { Difficulty } from "../types/api";
import { categoryClass, difficultyClass } from "../lib/tags";

type TagChipProps = {
  children: string;
  tone?: "category" | "difficulty" | "plain";
  category?: string;
  difficulty?: Difficulty;
};

export function TagChip({ children, tone = "plain", category, difficulty }: TagChipProps) {
  const toneClass =
    tone === "category" && category
      ? categoryClass(category)
      : tone === "difficulty" && difficulty
        ? difficultyClass(difficulty)
        : "bg-[var(--tag-bg)] text-[var(--tag-text)]";

  return (
    <span
      className={`inline-flex min-h-7 items-center rounded-full px-2.5 py-1 font-mono text-[11px] font-medium leading-none ${toneClass}`}
    >
      {children}
    </span>
  );
}
