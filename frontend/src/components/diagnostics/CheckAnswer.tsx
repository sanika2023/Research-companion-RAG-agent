import type { Check } from "@/lib/chat";
import { type RiskLevel, riskLevel } from "@/lib/diagnostics";

export const LEVEL_LABELS: Record<RiskLevel, string> = { low: "Low", medium: "Medium", high: "High" };

export const LEVEL_STYLES: Record<RiskLevel, string> = {
  low: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  medium: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
  high: "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
};

type Props = {
  check: Check;
  badgeId: string; // lets the drawer hand focus back to the badge when it closes
  onCheck: () => void;
  onOpen: () => void;
};

/** The "Check this answer" button, its progress, and the resulting risk badge. */
export function CheckAnswer({ check, badgeId, onCheck, onOpen }: Props) {
  switch (check.status) {
    case "idle":
      return (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onCheck}
            className="rounded-md border border-line-strong px-2 py-1 text-xs font-medium text-fg-soft hover:bg-subtle"
          >
            Check this answer
          </button>
          <span className="text-xs text-faint">
            Re-asks with small changes to see if the answer holds.
          </span>
        </div>
      );
    case "checking":
      return (
        <p role="status" className="mt-3 flex items-center gap-2 text-xs text-faint">
          <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden />
          Checking this answer… (usually 5–20 seconds)
        </p>
      );
    case "error":
      return (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <p role="alert" className="text-xs text-danger">
            {check.message}
          </p>
          <button
            type="button"
            onClick={onCheck}
            className="rounded-md border border-line-strong px-2 py-1 text-xs text-fg-soft hover:bg-subtle"
          >
            Try again
          </button>
        </div>
      );
    case "done": {
      const score = check.report.uncertainty;
      const level = score === null ? null : riskLevel(score);
      return (
        <button
          id={badgeId}
          type="button"
          aria-haspopup="dialog"
          onClick={onOpen}
          className={`mt-3 rounded-full border px-3 py-1 text-xs font-medium hover:brightness-95 ${
            level ? LEVEL_STYLES[level] : "border-line-strong bg-canvas text-fg-soft"
          }`}
        >
          {score === null || level === null
            ? "Hallucination risk: unknown"
            : `Hallucination risk: ${LEVEL_LABELS[level]} · ${score.toFixed(2)}`}
        </button>
      );
    }
  }
}
