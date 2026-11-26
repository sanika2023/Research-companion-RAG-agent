"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Chat } from "@/components/chat/Chat";
import { SplitPane } from "@/components/papers/SplitPane";
import type { PdfTarget } from "@/components/pdf-viewer/PdfViewer";
import { listDocuments, pdfUrl } from "@/lib/api";
import type { Citation, DocumentSummary } from "@/types/api";

// pdf.js needs browser APIs (canvas, workers), so the viewer is never rendered on the server.
const PdfViewer = dynamic(
  () => import("@/components/pdf-viewer/PdfViewer").then((m) => m.PdfViewer),
  { ssr: false, loading: () => <p className="p-4 text-sm text-muted">Loading viewer…</p> },
);

/** The dual-pane view for one paper: PDF on the left, chat on the right. */
export function PaperWorkspace({ docId }: { docId: string }) {
  const [paper, setPaper] = useState<DocumentSummary | null | "missing">(null);
  const [target, setTarget] = useState<PdfTarget | null>(null);
  const clicks = useRef(0);

  useEffect(() => {
    listDocuments()
      .then((papers) => setPaper(papers.find((p) => p.doc_id === docId) ?? "missing"))
      .catch(() => setPaper("missing"));
  }, [docId]);

  if (paper === "missing") {
    return (
      <div className="p-6 text-sm">
        <p role="alert" className="text-danger">
          This paper could not be found.
        </p>
        <Link href="/" className="text-link underline">
          Back to your papers
        </Link>
      </div>
    );
  }

  const showCitation = (citation: Citation) =>
    setTarget({ page: citation.page, bbox: citation.bbox, id: ++clicks.current });

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-line bg-surface px-4 text-sm">
        <Link href="/" className="text-faint hover:text-fg-soft">
          ← Papers
        </Link>
        <span className="truncate font-medium">{paper?.filename ?? "…"}</span>
      </div>
      <SplitPane
        start={
          <section aria-label="PDF viewer" className="h-full">
            <PdfViewer url={pdfUrl(docId)} target={target} />
          </section>
        }
        end={
          <section aria-label="Chat" className="h-full bg-canvas">
            {/* key: a different paper starts a fresh conversation */}
            <Chat key={docId} docId={docId} onCite={showCitation} />
          </section>
        }
      />
    </div>
  );
}
