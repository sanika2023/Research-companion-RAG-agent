import Link from "next/link";

import type { DocumentSummary } from "@/types/api";

function DocIcon() {
  return (
    <span
      aria-hidden
      className="grid size-9 shrink-0 place-items-center rounded-lg border border-accent-line bg-accent-soft text-on-accent-soft"
    >
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="size-4">
        <path d="M5 2.5h6.5L15 6v11.5H5z" strokeLinejoin="round" />
        <path d="M11.5 2.5V6H15M7.5 10h5M7.5 13h5" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function PaperList({ papers }: { papers: DocumentSummary[] }) {
  if (papers.length === 0) {
    return <p className="text-sm text-faint">No papers yet. Upload a PDF to get started.</p>;
  }
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface shadow-sm">
      {papers.map((paper) => (
        <li key={paper.doc_id}>
          <Link
            href={`/papers/${paper.doc_id}`}
            className="group flex items-center gap-4 px-5 py-4 hover:bg-accent-faint"
          >
            <DocIcon />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-fg-soft">{paper.filename}</span>
              <span className="block text-xs text-faint">
                {paper.page_count} pages · added{" "}
                {new Date(paper.created_at).toLocaleDateString()}
              </span>
            </span>
            <span
              aria-hidden
              className="text-faint transition group-hover:translate-x-0.5 group-hover:text-accent-ink"
            >
              →
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
