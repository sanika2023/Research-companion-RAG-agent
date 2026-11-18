import { API_URL } from "@/lib/config";
import type { DocumentSummary, DocumentUploaded } from "@/types/api";

export type Fetch = typeof fetch;

// Wrapped, not passed as `fetch` itself: a detached window.fetch throws "Illegal invocation".
export const browserFetch: Fetch = (input, init) => fetch(input, init);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function listDocuments(fetchFn: Fetch = browserFetch): Promise<DocumentSummary[]> {
  return parse(await fetchFn(`${API_URL}/documents`, { cache: "no-store" }));
}

export async function uploadDocument(
  file: File,
  fetchFn: Fetch = browserFetch,
): Promise<DocumentUploaded> {
  const form = new FormData();
  form.append("file", file);
  return parse(await fetchFn(`${API_URL}/documents`, { method: "POST", body: form }));
}

export function pdfUrl(docId: string): string {
  return `${API_URL}/documents/${docId}/file`;
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  return (await response.json()) as T;
}

/** The server's explanation (FastAPI's `detail`), or a generic message. */
export async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON; fall through
  }
  return `The server could not handle the request (HTTP ${response.status}).`;
}
