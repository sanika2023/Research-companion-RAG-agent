import type { AskResponse, DiagnoseRequest, Perturbation, Signal } from "@/types/api";

export type RiskLevel = "low" | "medium" | "high";

// Placeholder cut-offs from a handful of real answers (0.06-0.16); recalibrate in evaluation.
const MEDIUM_FROM = 0.2;
const HIGH_FROM = 0.4;

export function riskLevel(score: number): RiskLevel {
  if (score >= HIGH_FROM) return "high";
  return score >= MEDIUM_FROM ? "medium" : "low";
}

/** Only answers built from passages can be re-run; a refusal has nothing to check. */
export function canCheck(response: AskResponse): boolean {
  return !response.refused && response.passage_ids.length > 0;
}

export function checkRequest(response: AskResponse): DiagnoseRequest {
  return {
    question: response.question,
    answer: response.answer,
    passage_ids: response.passage_ids,
    sub_questions: response.sub_questions,
  };
}

export const PERTURBATIONS: Record<Perturbation, { title: string; description: string }> = {
  paraphrase: {
    title: "Reworded question",
    description: "The same question in different words.",
  },
  reorder: {
    title: "Passages reordered",
    description: "The same passages, in reverse order.",
  },
  distractor: {
    title: "Unrelated passage added",
    description: "An unrelated passage from the paper was added.",
  },
  drop_cited: {
    title: "Main source removed",
    description:
      "The passage the answer cites most was removed. Here a changed answer is good: it shows " +
      "the answer depended on its source.",
  },
};

const SKIPPED: Record<Perturbation, string> = {
  paraphrase: "Skipped.",
  reorder: "Skipped: only one passage was used, so there is no other order.",
  distractor: "Skipped: every passage of the paper was already used.",
  drop_cited: "Skipped: the answer cites no passage.",
};

/** Short remarks that explain a check's result beyond its number. */
export function signalNotes(signal: Signal): string[] {
  if (signal.status === "skipped") return [SKIPPED[signal.kind]];
  if (signal.status === "failed") return ["Failed: the model was unavailable for this check."];
  const notes: string[] = [];
  if (signal.refused) notes.push("The answer changed to “not found in the paper”.");
  if (signal.contradictions) {
    const claims = signal.contradictions === 1 ? "claim" : "claims";
    notes.push(`${signal.contradictions} ${claims} contradicted.`);
  }
  if (signal.weight === 0) notes.push("Shown for reference; not counted in the score.");
  return notes;
}
