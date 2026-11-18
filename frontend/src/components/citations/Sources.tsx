import type { Citation } from "@/types/api";

type Props = { citations: Citation[]; onCite: (citation: Citation) => void };

/** The passages an answer cites: click to show it in the PDF, expand to read it here. */
export function Sources({ citations, onCite }: Props) {
  if (citations.length === 0) return null;
  const sorted = [...citations].sort((a, b) => a.number - b.number);
  return (
    <section aria-label="Sources" className="mt-3 border-t border-stone-200 pt-2">
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-500">Sources</h4>
      <ul className="space-y-1">
        {sorted.map((citation) => (
          <li key={citation.number} className="text-sm">
            <button
              type="button"
              onClick={() => onCite(citation)}
              className="font-medium text-amber-900 hover:underline"
            >
              [{citation.number}] Page {citation.page}
            </button>
            <details className="ml-1 inline-block align-top text-stone-600 open:block">
              <summary className="cursor-pointer text-xs text-stone-500 hover:text-stone-800">
                Show passage
              </summary>
              <blockquote className="mt-1 border-l-2 border-amber-300 pl-2 text-xs whitespace-pre-line">
                {citation.text}
              </blockquote>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}
