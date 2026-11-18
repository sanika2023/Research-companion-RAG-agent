import { describe, expect, it } from "vitest";

import { type ChatState, chatReducer, isBusy, visibleAnswer } from "@/lib/chat";
import type { AskResponse, StreamEvent } from "@/types/api";

const RESPONSE: AskResponse = {
  doc_id: "d1",
  question: "Which datasets?",
  answer: "TruthfulQA [1].",
  citations: [{ number: 1, chunk_id: "c1", page: 9, text: "…", bbox: [[0, 0, 1, 1]] }],
  refused: false,
  sub_questions: [],
  flags: [],
};

function run(...events: StreamEvent[]): ChatState {
  let state = chatReducer({ turns: [] }, { type: "asked", id: "t1", question: "Which datasets?" });
  for (const event of events) state = chatReducer(state, { type: "event", id: "t1", event });
  return state;
}

const onlyTurn = (state: ChatState) => {
  const [turn] = state.turns;
  if (!turn) throw new Error("no turn");
  return turn;
};

describe("chatReducer", () => {
  it("starts a working turn when a question is asked", () => {
    const turn = onlyTurn(run());

    expect(turn).toMatchObject({ question: "Which datasets?", phase: "working", step: null });
  });

  it("tracks the current step and the sub-questions", () => {
    const turn = onlyTurn(
      run(
        { type: "status", step: "decompose" },
        { type: "sub_questions", subQuestions: ["A?", "B?"] },
        { type: "status", step: "retrieve" },
      ),
    );

    expect(turn.step).toBe("retrieve");
    expect(turn.subQuestions).toEqual(["A?", "B?"]);
  });

  it("shows tokens as they stream in", () => {
    const turn = onlyTurn(run({ type: "token", text: "Truthful" }, { type: "token", text: "QA" }));

    expect(visibleAnswer(turn)).toBe("TruthfulQA");
  });

  it("replaces the streamed text with the checked answer when done", () => {
    const turn = onlyTurn(
      run({ type: "token", text: "TruthfulQA [1][7]." }, { type: "done", response: RESPONSE }),
    );

    expect(turn.phase).toBe("done");
    expect(visibleAnswer(turn)).toBe("TruthfulQA [1].");
    expect(turn.response).toEqual(RESPONSE);
  });

  it("keeps partial text and the message when an error arrives", () => {
    const turn = onlyTurn(
      run({ type: "token", text: "Partial" }, { type: "error", message: "Model busy." }),
    );

    expect(turn.phase).toBe("error");
    expect(turn.error).toBe("Model busy.");
    expect(visibleAnswer(turn)).toBe("Partial");
  });

  it("marks a turn stopped when the user cancels", () => {
    const state = chatReducer(run({ type: "token", text: "Part" }), { type: "stopped", id: "t1" });

    expect(onlyTurn(state).phase).toBe("stopped");
  });

  it("ignores events that arrive after a turn has finished", () => {
    const state = chatReducer(run({ type: "done", response: RESPONSE }), {
      type: "event",
      id: "t1",
      event: { type: "token", text: "late" },
    });

    expect(visibleAnswer(onlyTurn(state))).toBe("TruthfulQA [1].");
  });

  it("only changes the turn the event belongs to", () => {
    let state = run({ type: "done", response: RESPONSE });
    state = chatReducer(state, { type: "asked", id: "t2", question: "Second?" });
    state = chatReducer(state, { type: "event", id: "t2", event: { type: "token", text: "B" } });

    expect(state.turns.map(visibleAnswer)).toEqual(["TruthfulQA [1].", "B"]);
  });

  it("is busy while the latest turn is working", () => {
    expect(isBusy(run())).toBe(true);
    expect(isBusy(run({ type: "done", response: RESPONSE }))).toBe(false);
    expect(isBusy({ turns: [] })).toBe(false);
  });
});
