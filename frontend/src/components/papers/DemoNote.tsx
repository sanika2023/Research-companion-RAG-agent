import type { PaperCredit } from "@/lib/demo-papers";

const external = { target: "_blank", rel: "noreferrer" } as const;

export function DemoNote({ credits }: { credits: PaperCredit[] }) {
  return (
    <section className="space-y-3 rounded-lg border border-accent-line bg-accent-faint px-4 py-3 text-sm text-fg-soft">
      <p>
        <span className="mr-2 rounded bg-accent-ink px-1.5 py-0.5 text-xs font-semibold tracking-wide text-surface uppercase">
          Demo mode
        </span>
        This demo has uploads turned off, so pick one of the papers below. To use your own papers,
        run Research Companion locally (see the README).
      </p>
      <div className="space-y-1.5">
        <p className="text-xs font-semibold text-muted">Paper credits</p>
        <ul className="space-y-1.5 text-xs leading-relaxed text-muted">
          {credits.map((paper) => (
            <li key={paper.arxivId}>
              <a
                href={`https://arxiv.org/abs/${paper.arxivId}`}
                className="italic underline-offset-2 hover:underline"
                {...external}
              >
                {paper.title}
              </a>{" "}
              by {paper.authors}, shared unmodified under{" "}
              <a href={paper.licenceUrl} className="underline underline-offset-2" {...external}>
                {paper.licence}
              </a>
              .
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
