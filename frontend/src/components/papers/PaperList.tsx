import Link from "next/link";

import type { DocumentSummary } from "@/types/api";

export function PaperList({ papers }: { papers: DocumentSummary[] }) {
  if (papers.length === 0) {
    return <p className="text-sm text-stone-500">No papers yet. Upload a PDF to get started.</p>;
  }
  return (
    <ul className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
      {papers.map((paper) => (
        <li key={paper.doc_id}>
          <Link
            href={`/papers/${paper.doc_id}`}
            className="flex items-baseline justify-between gap-4 px-4 py-3 hover:bg-amber-50"
          >
            <span className="truncate font-medium text-stone-800">{paper.filename}</span>
            <span className="shrink-0 text-xs text-stone-500">
              {paper.page_count} pages · added {new Date(paper.created_at).toLocaleDateString()}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
