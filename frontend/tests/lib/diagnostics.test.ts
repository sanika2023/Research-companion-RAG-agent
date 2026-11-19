// @vitest-environment node
import { describe, expect, it } from "vitest";

import { canCheck, checkRequest, riskLevel, signalNotes } from "@/lib/diagnostics";
import type { AskResponse, Signal } from "@/types/api";

const RESPONSE: AskResponse = {
  doc_id: "d1",
  question: "Which datasets?",
  answer: "TruthfulQA [1].",
  citations: [],
  refused: false,
  sub_questions: ["What datasets?"],
  flags: [],
  passage_ids: ["c1", "c2"],
};

function signal(overrides: Partial<Signal>): Signal {
  return {
    kind: "reorder",
    status: "ok",
    weight: 1,
    risk: 0.1,
    similarity: 0.9,
    claim_agreement: 1,
    contradictions: 0,
    question: "q",
    answer: "a",
    refused: false,
    ...overrides,
  };
}

describe("riskLevel", () => {
  it("is low below 0.2, medium below 0.4, and high from 0.4", () => {
    expect(riskLevel(0)).toBe("low");
    expect(riskLevel(0.19)).toBe("low");
    expect(riskLevel(0.2)).toBe("medium");
    expect(riskLevel(0.39)).toBe("medium");
    expect(riskLevel(0.4)).toBe("high");
    expect(riskLevel(1)).toBe("high");
  });
});

describe("canCheck", () => {
  it("allows checking an answer built from passages", () => {
    expect(canCheck(RESPONSE)).toBe(true);
  });

  it("does not offer a check for a refusal", () => {
    expect(canCheck({ ...RESPONSE, refused: true })).toBe(false);
  });

  it("does not offer a check when no passages were used", () => {
    expect(canCheck({ ...RESPONSE, passage_ids: [] })).toBe(false);
  });
});

describe("checkRequest", () => {
  it("sends back the question, answer, passages, and sub-questions", () => {
    expect(checkRequest(RESPONSE)).toEqual({
      question: "Which datasets?",
      answer: "TruthfulQA [1].",
      passage_ids: ["c1", "c2"],
      sub_questions: ["What datasets?"],
    });
  });
});

describe("signalNotes", () => {
  it("says why a check was skipped", () => {
    expect(signalNotes(signal({ kind: "distractor", status: "skipped", risk: null }))).toEqual([
      "Skipped: every passage of the paper was already used.",
    ]);
  });

  it("says when a check failed", () => {
    expect(signalNotes(signal({ status: "failed", risk: null }))).toEqual([
      "Failed: the model was unavailable for this check.",
    ]);
  });

  it("marks a check that is shown but not counted in the score", () => {
    expect(signalNotes(signal({ kind: "drop_cited", weight: 0 }))).toContain(
      "Shown for reference; not counted in the score.",
    );
  });

  it("points out contradicted claims", () => {
    expect(signalNotes(signal({ contradictions: 2 }))).toContain("2 claims contradicted.");
    expect(signalNotes(signal({ contradictions: 1 }))).toContain("1 claim contradicted.");
  });

  it("points out a run whose answer became a refusal", () => {
    expect(signalNotes(signal({ refused: true }))).toContain(
      "The answer changed to “not found in the paper”.",
    );
  });

  it("has nothing to add for a clean, counted run", () => {
    expect(signalNotes(signal({}))).toEqual([]);
  });
});
