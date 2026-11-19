import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Chat } from "@/components/chat/Chat";
import type { AskFn, DiagnoseFn } from "@/hooks/useAsk";
import { ApiError } from "@/lib/api";
import type { AskResponse, DiagnoseResponse } from "@/types/api";

// The full flow through Chat: the button, the check, the badge, and the drawer.

const RESPONSE: AskResponse = {
  doc_id: "d1",
  question: "Which datasets?",
  answer: "TruthfulQA [1].",
  citations: [{ number: 1, chunk_id: "c1", page: 9, text: "p", bbox: [] }],
  refused: false,
  sub_questions: [],
  flags: [],
  passage_ids: ["c1", "c2"],
};

const REPORT: DiagnoseResponse = {
  doc_id: "d1",
  uncertainty: 0.06,
  signals: [
    {
      kind: "paraphrase",
      status: "ok",
      weight: 1,
      risk: 0.04,
      similarity: 0.92,
      claim_agreement: 1,
      contradictions: 0,
      question: "What datasets were used?",
      answer: "TruthfulQA [2].",
      refused: false,
    },
  ],
  claims: ["MetaQA was evaluated on TruthfulQA."],
  flags: [],
};

const answers =
  (response: AskResponse): AskFn =>
  async function* () {
    yield { type: "done", response };
  };

/** A check that waits until the test settles it. */
function pendingCheck() {
  let settle: { resolve: (r: DiagnoseResponse) => void; reject: (e: Error) => void } | null = null;
  const diagnose: DiagnoseFn = vi.fn(
    () =>
      new Promise<DiagnoseResponse>((resolve, reject) => {
        settle = { resolve, reject };
      }),
  );
  return {
    diagnose,
    resolve: (report: DiagnoseResponse) => settle?.resolve(report),
    reject: (error: Error) => settle?.reject(error),
  };
}

async function askAndAnswer(diagnose: DiagnoseFn, response: AskResponse = RESPONSE) {
  render(<Chat docId="d1" ask={answers(response)} diagnose={diagnose} onCite={() => {}} />);
  await userEvent.type(screen.getByRole("textbox", { name: /question/i }), "Which datasets?{Enter}");
  await screen.findByText("Which datasets?");
}

const checkButton = () => screen.findByRole("button", { name: /check this answer/i });

describe("Checking an answer", () => {
  it("is offered for a finished answer but not run until asked", async () => {
    const diagnose = vi.fn<DiagnoseFn>();
    await askAndAnswer(diagnose);

    expect(await checkButton()).toBeInTheDocument();
    expect(diagnose).not.toHaveBeenCalled();
  });

  it("is not offered for a refusal", async () => {
    await askAndAnswer(vi.fn<DiagnoseFn>(), { ...RESPONSE, refused: true, passage_ids: [] });

    expect(await screen.findByRole("note")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check this answer/i })).toBeNull();
  });

  it("sends the answer and its passages, shows progress, then the risk", async () => {
    const check = pendingCheck();
    await askAndAnswer(check.diagnose);

    await userEvent.click(await checkButton());

    expect(check.diagnose).toHaveBeenCalledWith(
      "d1",
      {
        question: "Which datasets?",
        answer: "TruthfulQA [1].",
        passage_ids: ["c1", "c2"],
        sub_questions: [],
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(/checking this answer/i);
    expect(screen.queryByRole("button", { name: /check this answer/i })).toBeNull();

    check.resolve(REPORT);

    expect(
      await screen.findByRole("button", { name: "Hallucination risk: Low · 0.06" }),
    ).toBeInTheDocument();
  });

  it("explains a failed check and lets the user try again", async () => {
    const check = pendingCheck();
    await askAndAnswer(check.diagnose);
    await userEvent.click(await checkButton());

    check.reject(new ApiError(503, "The language model is busy."));

    expect(await screen.findByRole("alert")).toHaveTextContent("The language model is busy.");
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(check.diagnose).toHaveBeenCalledTimes(2);
  });

  it("explains an unreachable server in plain words", async () => {
    const check = pendingCheck();
    await askAndAnswer(check.diagnose);
    await userEvent.click(await checkButton());

    check.reject(new TypeError("Failed to fetch"));

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach the server/i);
  });

  it("opens the breakdown in a drawer and closes it with Escape", async () => {
    await askAndAnswer(vi.fn<DiagnoseFn>(async () => REPORT));
    await userEvent.click(await checkButton());
    const badge = await screen.findByRole("button", { name: /hallucination risk/i });

    await userEvent.click(badge);

    const drawer = screen.getByRole("dialog", { name: /answer check/i });
    expect(drawer).toHaveTextContent("Reworded question");
    expect(drawer).toHaveTextContent("MetaQA was evaluated on TruthfulQA.");

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(badge).toHaveFocus();
  });

  it("does not block asking the next question while a check runs", async () => {
    const check = pendingCheck();
    await askAndAnswer(check.diagnose);
    await userEvent.click(await checkButton());

    await userEvent.type(screen.getByRole("textbox", { name: /question/i }), "Next?");

    expect(screen.getByRole("button", { name: /^ask$/i })).toBeEnabled();
  });
});
