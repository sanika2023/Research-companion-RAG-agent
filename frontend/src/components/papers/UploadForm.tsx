"use client";

import { type ChangeEvent, useState } from "react";

import { ApiError, uploadDocument } from "@/lib/api";
import type { DocumentUploaded } from "@/types/api";

type Props = {
  upload?: (file: File) => Promise<DocumentUploaded>;
  onUploaded: (doc: DocumentUploaded) => void;
};

export function UploadForm({ upload = uploadDocument, onUploaded }: Props) {
  const [processing, setProcessing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow choosing the same file again after an error
    if (!file) return;
    setError(null);
    setProcessing(file.name);
    try {
      onUploaded(await upload(file));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Upload failed. Check that the backend is running.",
      );
    } finally {
      setProcessing(null);
    }
  }

  return (
    <div className="space-y-2">
      <label
        className={`inline-flex cursor-pointer items-center rounded-md bg-stone-800 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 has-disabled:cursor-wait has-disabled:bg-stone-400 has-focus-visible:outline-2 has-focus-visible:outline-amber-500`}
      >
        Upload a paper (PDF)
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={onChange}
          disabled={processing !== null}
          className="sr-only"
        />
      </label>
      {processing && (
        <p className="text-sm text-stone-600">
          Processing {processing}… reading, splitting and indexing the text takes about 20 seconds.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
