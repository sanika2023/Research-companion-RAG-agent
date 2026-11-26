import Markdown, { type Components } from "react-markdown";

type Props = {
  text: string;
  citedNumbers: number[] | null; // null while streaming: markers aren't verified yet
  onCite: (number: number) => void;
};

const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
const CITE_HREF = "#cite-";

/** Answer Markdown with verified `[n]` markers rendered as citation buttons. */
export function AnswerText({ text, citedNumbers, onCite }: Props) {
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITE_HREF)) {
        const number = Number(href.slice(CITE_HREF.length));
        return (
          <button
            type="button"
            aria-label={`Citation ${number}`}
            onClick={() => onCite(number)}
            className="mx-0.5 inline-flex min-w-5 items-center justify-center rounded bg-accent-soft px-1 align-baseline text-xs font-semibold text-on-accent-soft hover:bg-accent-soft-hover focus:outline-2 focus:outline-accent"
          >
            {children}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer" className="text-link underline">
          {children}
        </a>
      );
    },
  };
  return (
    <div className="answer text-sm leading-relaxed text-fg-soft">
      <Markdown components={components}>{linkCitations(text, citedNumbers)}</Markdown>
    </div>
  );
}

/** Rewrite `[1, 3]` as Markdown links `[1](#cite-1)[3](#cite-3)` so they render as buttons. */
function linkCitations(text: string, citedNumbers: number[] | null): string {
  if (!citedNumbers) return text;
  const cited = new Set(citedNumbers);
  return text.replace(MARKER, (marker, numbers: string) => {
    const parsed = numbers.split(",").map((n) => Number(n.trim()));
    // Leave anything that isn't a verified citation (e.g. "[2021]") as plain text.
    if (!parsed.every((n) => cited.has(n))) return marker;
    return parsed.map((n) => `[${n}](${CITE_HREF}${n})`).join("");
  });
}
