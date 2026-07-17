import type { Difficulty } from "../types/api";

export const categoryLabel: Record<string, string> = {
  "cs.LG": "cs.LG",
  "cs.AI": "cs.AI",
  "cs.CL": "cs.CL",
  "cs.CV": "cs.CV",
  "stat.ML": "stat.ML",
  "quant-ph": "quant-ph",
};

export function categoryClass(category: string): string {
  switch (category) {
    case "cs.LG":
      return "bg-[#eee6dc] text-[var(--accent-clay)]";
    case "cs.AI":
      return "bg-[#eee6dc] text-[#8b6b3d]";
    case "cs.CL":
      return "bg-[#ece4ed] text-[var(--accent-plum)]";
    case "cs.CV":
      return "bg-[#f0e2df] text-[var(--accent-rose)]";
    case "stat.ML":
      return "bg-[#ece8f0] text-[var(--accent-lavender)]";
    case "quant-ph":
      return "bg-[#e8ece3] text-[var(--accent-sage)]";
    default:
      return "bg-[var(--tag-bg)] text-[var(--tag-text)]";
  }
}

export function difficultyClass(difficulty: Difficulty): string {
  switch (difficulty) {
    case "beginner":
      return "bg-[#e8ece3] text-[var(--accent-sage)]";
    case "intermediate":
      return "bg-[#f1e7c9] text-[#8b6b3d]";
    case "expert":
      return "bg-[#ece4ed] text-[var(--accent-plum)]";
  }
}

export const filterOptions = [
  { id: "all", label: "All" },
  { id: "today", label: "Today" },
  { id: "week", label: "This Week" },
  { id: "saved", label: "Saved" },
  { id: "cs.AI", label: "cs.AI" },
  { id: "cs.LG", label: "cs.LG" },
  { id: "cs.CL", label: "cs.CL" },
  { id: "cs.CV", label: "cs.CV" },
  { id: "stat.ML", label: "stat.ML" },
  { id: "quant-ph", label: "quant-ph" },
] as const;

export type FilterId = (typeof filterOptions)[number]["id"];
