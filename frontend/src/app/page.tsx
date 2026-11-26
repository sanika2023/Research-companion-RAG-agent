"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PaperList } from "@/components/papers/PaperList";
import { UploadForm } from "@/components/papers/UploadForm";
import { listDocuments } from "@/lib/api";
import { API_URL } from "@/lib/config";
import type { DocumentSummary } from "@/types/api";

export default function HomePage() {
  const router = useRouter();
  const [papers, setPapers] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    listDocuments()
      .then(setPapers)
      .catch(() => setError(true));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">Your papers</h1>
        <p className="text-sm text-muted">
          Pick a paper to ask questions about it. Every answer links to the exact passages it
          used, so you can check it yourself.
        </p>
      </section>

      <UploadForm onUploaded={(doc) => router.push(`/papers/${doc.doc_id}`)} />

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
