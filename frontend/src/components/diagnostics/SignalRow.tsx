import { PERTURBATIONS, signalNotes } from "@/lib/diagnostics";
import type { Signal } from "@/types/api";

const percent = (value: number) => `${Math.round(value * 100)}%`;

/** One perturbation: what changed, how risky the result looked, and the answer it produced. */
export function SignalRow({ signal }: { signal: Signal }) {
  const { title, description } = PERTURBATIONS[signal.kind];
  const measures = [
    signal.similarity !== null && `similarity ${signal.similarity.toFixed(2)}`,
    signal.claim_agreement !== null && `claims agreed ${percent(signal.claim_agreement)}`,
  ].filter(Boolean);

  return (
    <li className="space-y-1 border-t border-line py-3 first:border-t-0">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {signal.risk !== null && (
          <span className="text-xs whitespace-nowrap text-muted tabular-nums">
            risk {signal.risk.toFixed(2)}
          </span>
        )}
      </div>
      {signal.risk !== null && <RiskBar value={signal.risk} muted={signal.weight === 0} />}
      <p className="text-xs text-faint">{description}</p>
      {measures.length > 0 && <p className="text-xs text-faint">{measures.join(" · ")}</p>}
      {signalNotes(signal).map((note) => (
        <p key={note} className="text-xs text-warn">
          {note}
        </p>
      ))}
      {signal.answer && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted hover:text-fg">
            Show answer
          </summary>
          <div className="mt-1 space-y-1 rounded bg-canvas p-2">
            {signal.kind === "paraphrase" && signal.question && (
              <p>
                <span className="text-faint">Asked: </span>
                <span>{signal.question}</span>
              </p>
            )}
            {/* Plain text: citation numbers here refer to the reshuffled passages, not the PDF. */}
            <p className="whitespace-pre-wrap">{signal.answer}</p>
          </div>
        </details>
      )}
    </li>
  );
}

export function RiskBar({ value, muted = false }: { value: number; muted?: boolean }) {
  return (
    <div className="h-1.5 rounded-full bg-sunken" aria-hidden>
      <div
        className={`h-full rounded-full ${muted ? "bg-faint" : "bg-fg-soft"}`}
        style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }}
      />
    </div>
  );
}
