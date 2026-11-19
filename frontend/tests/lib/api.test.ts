// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { ApiError, diagnoseAnswer, listDocuments, pdfUrl, uploadDocument } from "@/lib/api";
import type { DiagnoseRequest } from "@/types/api";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api", () => {
  it("lists documents", async () => {
    const docs = [{ doc_id: "d1", filename: "a.pdf", page_count: 3, chunk_count: 9, created_at: "x" }];
    const fetchFn = vi.fn(async () => json(docs));

    expect(await listDocuments(fetchFn)).toEqual(docs);
    expect(fetchFn).toHaveBeenCalledWith("http://localhost:8000/documents", expect.anything());
  });

  it("uploads a PDF as multipart form data", async () => {
    const uploaded = { doc_id: "d1", filename: "a.pdf", page_count: 3, chunk_count: 9 };
    const fetchFn = vi.fn(async () => json(uploaded, 201));
    const file = new File(["%PDF-"], "a.pdf", { type: "application/pdf" });

    expect(await uploadDocument(file, fetchFn)).toEqual(uploaded);
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/documents");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("raises the server's explanation when an upload is rejected", async () => {
    const fetchFn = async () => json({ detail: "PDF has no extractable text" }, 400);
    const file = new File(["x"], "scan.pdf");

    await expect(uploadDocument(file, fetchFn)).rejects.toEqual(
      new ApiError(400, "PDF has no extractable text"),
    );
  });

  it("builds the URL of a paper's PDF", () => {
    expect(pdfUrl("d1")).toBe("http://localhost:8000/documents/d1/file");
  });

  it("sends an answer to be checked as JSON and returns the report", async () => {
    const report = { doc_id: "d1", uncertainty: 0.1, signals: [], claims: [], flags: [] };
    const fetchFn = vi.fn(async () => json(report));
    const request: DiagnoseRequest = {
      question: "q",
      answer: "a [1].",
      passage_ids: ["c1"],
      sub_questions: [],
    };
    const signal = new AbortController().signal;

    expect(await diagnoseAnswer("d1", request, { signal, fetchFn })).toEqual(report);
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/documents/d1/diagnose");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(request);
    expect(init.signal).toBe(signal);
  });

  it("raises the server's explanation when a check fails", async () => {
    const fetchFn = async () => json({ detail: "The language model is busy." }, 503);
    const request = { question: "q", answer: "a", passage_ids: ["c1"], sub_questions: [] };

    await expect(diagnoseAnswer("d1", request, { fetchFn })).rejects.toEqual(
      new ApiError(503, "The language model is busy."),
    );
  });
});
