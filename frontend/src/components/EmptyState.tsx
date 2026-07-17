import { motion } from "framer-motion";

import { notebookEase } from "../lib/motion";
import { useReducedMotionSafe } from "../hooks/useReducedMotionSafe";

type EmptyStateProps = {
  title?: string;
  detail?: string;
};

export function EmptyState({ title = "Nothing new today.", detail }: EmptyStateProps) {
  const reducedMotion = useReducedMotionSafe();

  return (
    <div className="flex min-h-80 flex-col items-center justify-center rounded-[14px] border border-dashed border-[var(--border-strong)] bg-[rgba(255,250,243,0.58)] px-6 text-center">
      <motion.svg
        viewBox="0 0 120 92"
        className="mb-4 h-24 w-32 text-[var(--border-strong)]"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3"
      >
        <motion.path
          d="M34 38h42v18c0 13-9 22-21 22S34 69 34 56V38Z"
          initial={reducedMotion ? false : { pathLength: 0 }}
          animate={reducedMotion ? undefined : { pathLength: 1 }}
          transition={{ duration: 1, ease: notebookEase }}
        />
        <motion.path
          d="M76 45h8c8 0 8 14 0 14h-8"
          initial={reducedMotion ? false : { pathLength: 0 }}
          animate={reducedMotion ? undefined : { pathLength: 1 }}
          transition={{ delay: 0.15, duration: 0.8, ease: notebookEase }}
        />
        <motion.path
          d="M28 82h58"
          initial={reducedMotion ? false : { pathLength: 0 }}
          animate={reducedMotion ? undefined : { pathLength: 1 }}
          transition={{ delay: 0.25, duration: 0.6, ease: notebookEase }}
        />
        <motion.path
          d="M44 26c-5-7 5-9 0-16M58 26c-5-7 5-9 0-16M72 26c-5-7 5-9 0-16"
          initial={reducedMotion ? false : { pathLength: 0 }}
          animate={reducedMotion ? undefined : { pathLength: 1 }}
          transition={{ delay: 0.35, duration: 1, ease: notebookEase }}
        />
      </motion.svg>
      <h2 className="font-serif text-2xl text-[var(--text-ink)]">{title}</h2>
      {detail ? <p className="mt-2 max-w-sm text-sm text-[var(--text-note)]">{detail}</p> : null}
    </div>
  );
}
