// Mirrors the backend's Pydantic schemas (backend/app/schemas/).

export type DocumentSummary = {
  doc_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
};

export type DocumentUploaded = Omit<DocumentSummary, "created_at">;

export type Citation = {
  number: number; // the [n] used in the answer text
  chunk_id: string;
  page: number; // 1-based
  text: string;
  bbox: number[][]; // [x0, y0, x1, y1] per text block, PDF points from the top-left
};

export type AskResponse = {
  doc_id: string;
  question: string;
  answer: string;
  citations: Citation[];
  refused: boolean;
  sub_questions: string[];
  flags: string[];
  passage_ids: string[]; // every passage the model saw, in order; sent back to /diagnose
};

export type Perturbation = "paraphrase" | "reorder" | "distractor" | "drop_cited";

export type DiagnoseRequest = {
  question: string;
  answer: string;
  passage_ids: string[];
  sub_questions: string[];
};

export type Signal = {
  kind: Perturbation;
  status: "ok" | "skipped" | "failed";
  weight: number; // share of the overall score; 0 = shown but not scored
  risk: number | null; // 0 = behaved as a reliable answer should, 1 = did not
  similarity: number | null; // embedding similarity to the original, rescaled 0-1
  claim_agreement: number | null; // fraction of the original's claims this run agrees with
  contradictions: number | null;
  question: string | null; // asked in this run; reworded for paraphrase
  answer: string | null; // the perturbed answer
  refused: boolean;
};

export type DiagnoseResponse = {
  doc_id: string;
  uncertainty: number | null; // 0-1; null when no scored check could be measured
  signals: Signal[];
  claims: string[];
  flags: string[]; // e.g. "judge_failed"
};

export type Step = "classify" | "decompose" | "retrieve" | "synthesize";

export type StreamEvent =
  | { type: "status"; step: Step }
  | { type: "sub_questions"; subQuestions: string[] }
  | { type: "token"; text: string }
  | { type: "done"; response: AskResponse }
  | { type: "error"; message: string };
