# 0005: Streaming answers with Server-Sent Events

## Context
An answer takes several seconds (classification, search, generation), and up to a minute when
Gemini is slow. The chat should show progress and the answer as it is written. But citations
can only be verified once the whole answer exists, and the model signals "not in this paper"
with a `NOT_FOUND` code word that users should never see.

## Decision
- **Server-Sent Events over a POST** (`/documents/{doc_id}/ask/stream`), using FastAPI's
  built-in `EventSourceResponse` (keep-alive pings included). Events: `status`,
  `sub_questions`, `token`, then exactly one of `done` or `error`.
- **`done` is authoritative:** it carries the same citation-checked result as `/ask`, and the
  client replaces the streamed text with it.
- **Hold back `NOT_FOUND`:** text is withheld while it could still be the code word.
- **One graph for both endpoints:** the synthesize node always streams from the model and
  writes pieces to LangGraph's stream writer (a no-op under `ainvoke`); `stream_answer` maps
  LangGraph's `tasks`/`custom`/`values` stream modes to our events.
- **Retry only before the first chunk;** later failures end the stream with `error`.
- **404 before streaming:** the paper's existence is checked in a dependency, because once
  the stream starts the status code is already 200.
- `/ask` stays for scripts and the evaluation.

## Alternatives considered
- **WebSockets:** two-way, but we only need server → client; SSE is plain HTTP, simpler to
  test and to proxy.
- **GET + browser `EventSource`:** would allow automatic reconnects, but puts the question in
  the URL (length limits, logs) and skips the request-body validation shared with `/ask`.
- **Checking citations live, marker by marker:** a cleaner live view, but duplicates the
  checker's logic for a case that did not occur in testing; the final swap is simpler.
- **`sse-starlette`:** a common library, unnecessary since FastAPI now supports SSE.
