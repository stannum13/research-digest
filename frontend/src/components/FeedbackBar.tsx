import { ThumbsDown, ThumbsUp, BookmarkCheck, EyeOff } from "lucide-react";

import { useFeedbackMutation } from "../hooks/useDigestApi";
import type { FeedbackSignal } from "../types/api";

const feedbackItems: Array<{ signal: FeedbackSignal; label: string; icon: typeof ThumbsUp }> = [
  { signal: "more_like_this", label: "More like this", icon: ThumbsUp },
  { signal: "less_like_this", label: "Less like this", icon: ThumbsDown },
  { signal: "important", label: "Important", icon: BookmarkCheck },
  { signal: "hide", label: "Hide", icon: EyeOff },
];

export function FeedbackBar({ arxivId }: { arxivId: string }) {
  const feedback = useFeedbackMutation(arxivId);

  return (
    <div className="flex flex-wrap gap-2 border-t border-[var(--border-warm)] pt-4">
      {feedbackItems.map(({ signal, label, icon: Icon }) => (
        <button
          key={signal}
          type="button"
          className="inline-flex items-center gap-2 rounded-full border border-[var(--border-warm)] px-3 py-2 font-mono text-[11px] text-[var(--text-note)] transition hover:border-[var(--accent-clay)] hover:text-[var(--accent-clay)]"
          onClick={() => feedback.mutate({ signal })}
          disabled={feedback.isPending}
        >
          <Icon size={13} aria-hidden="true" />
          {label}
        </button>
      ))}
    </div>
  );
}
