"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PaperList } from "@/components/papers/PaperList";
import { UploadForm } from "@/components/papers/UploadForm";
import { getFeatures, listDocuments } from "@/lib/api";
import { API_URL } from "@/lib/config";
import type { DocumentSummary, Features } from "@/types/api";

export default function HomePage() {
  const router = useRouter();
  const [papers, setPapers] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [features, setFeatures] = useState<Features | null>(null);

  useEffect(() => {
    listDocuments()
      .then(setPapers)
      .catch(() => setError(true));
    // Unknown until the server answers; uploads stay hidden so the demo never flashes them.
    // On failure, the papers request above already reports the unreachable backend.
    getFeatures()
      .then(setFeatures)
      .catch(() => undefined);
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-12">
      <section className="space-y-3">
        <p className="text-xs font-semibold tracking-[0.16em] text-accent-ink uppercase">
          Library
        </p>
        <h1 className="font-serif text-4xl font-semibold tracking-tight">Your papers</h1>
        <p className="max-w-prose leading-relaxed text-muted">
          Pick a paper to ask questions about it. Every answer links to the exact passages it
          used, so you can check it yourself.
        </p>
      </section>

      {features?.uploads_enabled ? (
        <UploadForm onUploaded={(doc) => router.push(`/papers/${doc.doc_id}`)} />
      ) : features ? (
        <p className="rounded-lg border border-accent-line bg-accent-faint px-4 py-3 text-sm text-fg-soft">
          This demo has uploads turned off, so pick one of the papers below. To use your own
          papers, run Research Companion locally (see the README).
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-danger">
          Can&apos;t reach the backend at {API_URL}. Is it running?
        </p>
      ) : papers === null ? (
        <p className="text-sm text-faint">Loading papers…</p>
      ) : (
        <PaperList papers={papers} />
      )}
    </div>
  );
}
