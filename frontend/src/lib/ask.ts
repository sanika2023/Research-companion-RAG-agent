import { browserFetch, errorMessage, type Fetch } from "@/lib/api";
import { API_URL } from "@/lib/config";
import { SseParser, type RawEvent } from "@/lib/sse";
import type { AskResponse, Step, StreamEvent } from "@/types/api";

type Options = { fetchFn?: Fetch; signal?: AbortSignal };

const UNREACHABLE = "Could not reach the server. Check that the backend is running.";
const LOST = "The connection was lost before the answer finished. Please try again.";

/**
 * Ask a question about one paper and yield the answer's events as they arrive.
 * Every failure becomes a final `error` event, so callers handle one failure path.
 * The browser's EventSource can't send a POST body, hence fetch + a manual SSE parser.
 */
export async function* askStream(
  docId: string,
  question: string,
  { fetchFn = browserFetch, signal }: Options = {},
): AsyncGenerator<StreamEvent> {
  let response: Response;
  try {
    response = await fetchFn(`${API_URL}/documents/${docId}/ask/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch {
    if (!signal?.aborted) yield { type: "error", message: UNREACHABLE };
    return;
  }
  if (!response.ok || !response.body) {
    yield { type: "error", message: await errorMessage(response) };
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SseParser();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const raw of parser.push(value)) {
        const event = toStreamEvent(raw);
        if (!event) continue;
        yield event;
        if (event.type === "done" || event.type === "error") return;
      }
    }
  } catch {
    if (signal?.aborted) return; // the user cancelled; nothing to report
  } finally {
    reader.cancel().catch(() => {}); // stop downloading if we finished early
  }
  yield { type: "error", message: LOST };
}

function toStreamEvent({ event, data }: RawEvent): StreamEvent | null {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (event) {
    case "status":
      return { type: "status", step: payload.step as Step };
    case "sub_questions":
      return { type: "sub_questions", subQuestions: payload.sub_questions as string[] };
    case "token":
      return { type: "token", text: payload.text as string };
    case "done":
      return { type: "done", response: payload as unknown as AskResponse };
    case "error":
      return { type: "error", message: payload.message as string };
    default:
      return null; // newer server event this client doesn't know yet
  }
}
