import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Chat } from "@/components/chat/Chat";
import type { AskFn } from "@/hooks/useAsk";
import type { AskResponse, Citation, StreamEvent } from "@/types/api";

const CITATION: Citation = { number: 1, chunk_id: "c1", page: 9, text: "p", bbox: [] };
const RESPONSE: AskResponse = {
  doc_id: "d1",
  question: "Which datasets?",
  answer: "TruthfulQA [1].",
  citations: [CITATION],
  refused: false,
  sub_questions: [],
  flags: [],
  passage_ids: ["c1"],
};

function scripted(...events: StreamEvent[]): AskFn {
  return async function* () {
    yield* events;
  };
}

/** An ask that stays open after its first events, to observe the in-progress UI. */
function held(...first: StreamEvent[]) {
  let release: () => void = () => {};
  const finished = new Promise<void>((resolve) => {
    release = resolve;
  });
  const ask: AskFn = async function* (_docId, _question, { signal }) {
    yield* first;
    const aborted = new Promise<void>((resolve) => signal.addEventListener("abort", () => resolve()));
    await Promise.race([finished, aborted]);
  };
  return { ask, finish: () => release() };
}

async function askQuestion(text = "Which datasets?") {
  await userEvent.type(screen.getByRole("textbox", { name: /question/i }), `${text}{Enter}`);
}

describe("Chat", () => {
  it("shows the question and the cited answer", async () => {
    render(<Chat docId="d1" ask={scripted({ type: "done", response: RESPONSE })} onCite={() => {}} />);

    await askQuestion();

    expect(await screen.findByText("Which datasets?")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Citation 1" })).toBeInTheDocument();
  });

  it("passes the paper and the trimmed question to ask", async () => {
    const ask = vi.fn(scripted({ type: "done", response: RESPONSE }));
    render(<Chat docId="d1" ask={ask} onCite={() => {}} />);

    await askQuestion("  Why?  ");

    expect(ask).toHaveBeenCalledWith(
      "d1",
      "Why?",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows progress and sub-questions while working, and blocks a second question", async () => {
    const { ask, finish } = held(
      { type: "status", step: "decompose" },
      { type: "sub_questions", subQuestions: ["What datasets?"] },
      { type: "status", step: "retrieve" },
    );
    render(<Chat docId="d1" ask={ask} onCite={() => {}} />);

    await askQuestion();

    expect(await screen.findByText(/searching the paper/i)).toBeInTheDocument();
    expect(screen.getByText("What datasets?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^ask$/i })).toBeDisabled();
    finish();
  });

  it("can stop an answer in progress", async () => {
    const { ask } = held({ type: "token", text: "Partial" });
    render(<Chat docId="d1" ask={ask} onCite={() => {}} />);
    await askQuestion();

    await userEvent.click(await screen.findByRole("button", { name: /stop/i }));

    expect(await screen.findByText(/stopped/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /stop/i })).toBeNull();
  });

  it("reports which citation was clicked", async () => {
    const onCite = vi.fn();
    render(<Chat docId="d1" ask={scripted({ type: "done", response: RESPONSE })} onCite={onCite} />);
    await askQuestion();

    await userEvent.click(await screen.findByRole("button", { name: "Citation 1" }));

    expect(onCite).toHaveBeenCalledWith(CITATION);
  });

  it("shows a refusal as a notice, not as an answer", async () => {
    const refused: AskResponse = {
      ...RESPONSE,
      answer: "I couldn't find the answer.",
      citations: [],
      refused: true,
    };
    render(<Chat docId="d1" ask={scripted({ type: "done", response: refused })} onCite={() => {}} />);

    await askQuestion();

    expect(await screen.findByRole("note")).toHaveTextContent("I couldn't find the answer.");
  });

  it("shows errors", async () => {
    render(
      <Chat docId="d1" ask={scripted({ type: "error", message: "Model busy." })} onCite={() => {}} />,
    );

    await askQuestion();

    expect(await screen.findByRole("alert")).toHaveTextContent("Model busy.");
  });

  it("does not send a blank question", async () => {
    const ask = vi.fn(scripted());
    render(<Chat docId="d1" ask={ask} onCite={() => {}} />);

    await askQuestion("   ");

    expect(ask).not.toHaveBeenCalled();
  });
});
