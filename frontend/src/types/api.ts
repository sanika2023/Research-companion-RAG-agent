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
};

export type Step = "classify" | "decompose" | "retrieve" | "synthesize";

export type StreamEvent =
  | { type: "status"; step: Step }
  | { type: "sub_questions"; subQuestions: string[] }
  | { type: "token"; text: string }
  | { type: "done"; response: AskResponse }
  | { type: "error"; message: string };
