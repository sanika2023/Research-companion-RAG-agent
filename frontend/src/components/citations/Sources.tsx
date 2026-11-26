import type { Citation } from "@/types/api";

type Props = { citations: Citation[]; onCite: (citation: Citation) => void };

/** The passages an answer cites: click to show it in the PDF, expand to read it here. */
export function Sources({ citations, onCite }: Props) {
  if (citations.length === 0) return null;
  const sorted = [...citations].sort((a, b) => a.number - b.number);
  return (
    <section aria-label="Sources" className="mt-3 border-t border-line pt-2">
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">Sources</h4>
      <ul className="space-y-1">
        {sorted.map((citation) => (
          <li key={citation.number} className="text-sm">
            <button
              type="button"
              onClick={() => onCite(citation)}
              className="font-medium text-on-accent-soft hover:underline"
            >
              [{citation.number}] Page {citation.page}
            </button>
            <details className="ml-1 inline-block align-top text-muted open:block">
              <summary className="cursor-pointer text-xs text-faint hover:text-fg-soft">
                Show passage
              </summary>
              <blockquote className="mt-1 border-l-2 border-accent-line pl-2 text-xs whitespace-pre-line">
                {citation.text}
              </blockquote>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}
