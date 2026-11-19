import type { AskResponse, DiagnoseResponse, Step, StreamEvent } from "@/types/api";

/** The optional "Check this answer" run for a finished answer. */
export type Check =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "done"; report: DiagnoseResponse }
  | { status: "error"; message: string };

export type Turn = {
  id: string;
  question: string;
  phase: "working" | "done" | "error" | "stopped";
  step: Step | null;
  subQuestions: string[];
  streamedText: string; // raw tokens; replaced by response.answer once done
  response: AskResponse | null;
  error: string | null;
  check: Check;
};

export type ChatState = { turns: Turn[] };

export type ChatAction =
  | { type: "asked"; id: string; question: string }
  | { type: "event"; id: string; event: StreamEvent }
  | { type: "stopped"; id: string }
  | { type: "check"; id: string; check: Check };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  if (action.type === "asked") {
    const turn: Turn = {
      id: action.id,
      question: action.question,
      phase: "working",
      step: null,
      subQuestions: [],
      streamedText: "",
      response: null,
      error: null,
      check: { status: "idle" },
    };
    return { turns: [...state.turns, turn] };
  }
  if (action.type === "check") {
    // Checks happen after the answer is final, so they bypass the finished-turn rule below.
    const { id, check } = action;
    return {
      turns: state.turns.map((turn) =>
        turn.id === id && turn.phase === "done" ? { ...turn, check } : turn,
      ),
    };
  }
  return {
    turns: state.turns.map((turn) =>
      // A finished turn is final: late events (e.g. after Stop) must not change it.
      turn.id === action.id && turn.phase === "working" ? applyAction(turn, action) : turn,
    ),
  };
}

function applyAction(
  turn: Turn,
  action: Extract<ChatAction, { type: "event" } | { type: "stopped" }>,
): Turn {
  if (action.type === "stopped") return { ...turn, phase: "stopped" };
  const event = action.event;
  switch (event.type) {
    case "status":
      return { ...turn, step: event.step };
    case "sub_questions":
      return { ...turn, subQuestions: event.subQuestions };
    case "token":
      return { ...turn, streamedText: turn.streamedText + event.text };
    case "done":
      return { ...turn, phase: "done", response: event.response };
    case "error":
      return { ...turn, phase: "error", error: event.message };
  }
}

/** The checked answer once available, otherwise the text streamed so far. */
export function visibleAnswer(turn: Turn): string {
  return turn.response?.answer ?? turn.streamedText;
}

export function isBusy(state: ChatState): boolean {
  return state.turns.at(-1)?.phase === "working";
}
