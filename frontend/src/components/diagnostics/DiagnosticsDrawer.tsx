import { useEffect, useId, useRef } from "react";

import { LEVEL_LABELS, LEVEL_STYLES } from "@/components/diagnostics/CheckAnswer";
import { RiskBar, SignalRow } from "@/components/diagnostics/SignalRow";
import { riskLevel } from "@/lib/diagnostics";
import type { DiagnoseResponse } from "@/types/api";

type Props = { question: string; report: DiagnoseResponse; onClose: () => void };

/** Side panel over the chat with the answer check's score and per-check breakdown. */
export function DiagnosticsDrawer({ question, report, onClose }: Props) {
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  const score = report.uncertainty;

  useEffect(() => {
    close.current?.focus(); // keyboard and screen-reader users land inside the drawer
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="absolute inset-0 z-10 flex justify-end">
      <div className="absolute inset-0 bg-stone-900/20" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative flex h-full w-full max-w-md flex-col bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
          <h2 id={titleId} className="font-semibold">
            Answer check
          </h2>
          <button
            ref={close}
            type="button"
            onClick={onClose}
            aria-label="Close answer check"
            className="rounded px-2 text-lg leading-none text-stone-500 hover:bg-stone-100 hover:text-stone-900"
          >
            ×
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
          <p className="text-xs text-stone-500">
            Question: <span className="text-stone-800">{question}</span>
          </p>

          <section className="space-y-2">
            {score === null ? (
              <p className="text-sm text-stone-700">
                Not enough checks succeeded to give a score. The details below show what ran.
              </p>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Hallucination risk</span>
                  <span
                    className={`rounded-full border px-2 text-xs font-medium ${LEVEL_STYLES[riskLevel(score)]}`}
                  >
                    {LEVEL_LABELS[riskLevel(score)]}
                  </span>
                  <span className="ml-auto text-sm tabular-nums">{score.toFixed(2)}</span>
                </div>
                <RiskBar value={score} />
              </>
            )}
            <p className="text-xs text-stone-600">
              We asked again with one small change at a time and compared the answers. A reliable
              answer stays the same, so it scores near 0. This measures consistency, not
              correctness: an answer can be wrong in the same way every time.
            </p>
            {report.flags.includes("judge_failed") && (
              <p className="text-xs text-amber-800">
                Claim-by-claim comparison was unavailable, so the score uses text similarity only.
              </p>
            )}
          </section>

          <section>
            <h3 className="sr-only">Checks</h3>
            <ul>
              {report.signals.map((signal) => (
                <SignalRow key={signal.kind} signal={signal} />
              ))}
            </ul>
          </section>

          {report.claims.length > 0 && (
            <section className="space-y-1">
              <h3 className="text-sm font-medium">Claims compared</h3>
              <ul className="ml-4 list-disc space-y-1 text-xs text-stone-700">
                {report.claims.map((claim) => (
                  <li key={claim}>{claim}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
