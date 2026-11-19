// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { askStream } from "@/lib/ask";
import type { AskResponse, StreamEvent } from "@/types/api";

const DONE: AskResponse = {
  doc_id: "d1",
  question: "q",
  answer: "A [1].",
  citations: [],
  refused: false,
  sub_questions: [],
  flags: [],
  passage_ids: ["c1"],
};

function streamOf(...chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { headers: { "content-type": "text/event-stream" } });
}

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

async function collect(fetchFn: typeof fetch): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  for await (const event of askStream("d1", "q", { fetchFn })) events.push(event);
  return events;
}

describe("askStream", () => {
  it("posts the question to the paper's stream endpoint", async () => {
    const fetchFn = vi.fn(async () => streamOf(sse("done", DONE)));

    await collect(fetchFn);

    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/documents/d1/ask/stream");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ question: "q" });
  });

  it("yields typed events in order", async () => {
    const fetchFn = async () =>
      streamOf(
        sse("status", { step: "decompose" }),
        sse("sub_questions", { sub_questions: ["A?", "B?"] }),
        sse("token", { text: "A " }) + sse("token", { text: "[1]." }),
        sse("done", DONE),
      );

    expect(await collect(fetchFn)).toEqual([
      { type: "status", step: "decompose" },
      { type: "sub_questions", subQuestions: ["A?", "B?"] },
      { type: "token", text: "A " },
      { type: "token", text: "[1]." },
      { type: "done", response: DONE },
    ]);
  });

  it("passes on the server's error event", async () => {
    const fetchFn = async () => streamOf(sse("error", { message: "Model busy." }));

    expect(await collect(fetchFn)).toEqual([{ type: "error", message: "Model busy." }]);
  });

  it("turns an HTTP error into an error event with the server's detail", async () => {
    const fetchFn = async () =>
      new Response(JSON.stringify({ detail: "document not found" }), { status: 404 });

    expect(await collect(fetchFn)).toEqual([{ type: "error", message: "document not found" }]);
  });

  it("turns an unreachable server into an error event", async () => {
    const fetchFn = async () => {
      throw new TypeError("Failed to fetch");
    };

    const [event] = await collect(fetchFn);

    expect(event).toMatchObject({ type: "error" });
    expect((event as { message: string }).message).toMatch(/reach the server/i);
  });

  it("reports a stream that stops before the answer is finished", async () => {
    const fetchFn = async () => streamOf(sse("token", { text: "Partial" }));

    const events = await collect(fetchFn);

    expect(events.at(-1)).toMatchObject({ type: "error" });
    expect((events.at(-1) as { message: string }).message).toMatch(/connection was lost/i);
  });

  it("ignores events it does not know", async () => {
    const fetchFn = async () => streamOf(sse("future_thing", { x: 1 }), sse("done", DONE));

    expect(await collect(fetchFn)).toEqual([{ type: "done", response: DONE }]);
  });

  it("ends quietly when the user cancels", async () => {
    const controller = new AbortController();
    const fetchFn = async () => {
      controller.abort();
      throw new DOMException("aborted", "AbortError");
    };
    const events: StreamEvent[] = [];

    for await (const event of askStream("d1", "q", { fetchFn, signal: controller.signal })) {
      events.push(event);
    }

    expect(events).toEqual([]);
  });
});
