"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { askStream } from "@/lib/ask";
import { chatReducer } from "@/lib/chat";
import type { StreamEvent } from "@/types/api";

export type AskFn = (
  docId: string,
  question: string,
  options: { signal: AbortSignal },
) => AsyncIterable<StreamEvent>;

/** Chat state for one paper: ask questions (one at a time) and stop the current answer. */
export function useAsk(docId: string, ask: AskFn = askStream) {
  const [state, dispatch] = useReducer(chatReducer, { turns: [] });
  const current = useRef<{ id: string; controller: AbortController } | null>(null);
  const nextId = useRef(0);

  // Leaving the page cancels the request, so the server stops generating.
  useEffect(() => () => current.current?.controller.abort(), []);

  const submit = useCallback(
    async (question: string) => {
      const id = `turn-${nextId.current++}`;
      const controller = new AbortController();
      current.current = { id, controller };
      dispatch({ type: "asked", id, question });
      try {
        for await (const event of ask(docId, question, { signal: controller.signal })) {
          dispatch({ type: "event", id, event });
        }
      } catch {
        // askStream reports failures as events; this only guards against a misbehaving ask.
      }
      if (!controller.signal.aborted) {
        // No-op if the turn already finished (the reducer ignores events for finished turns).
        const event: StreamEvent = { type: "error", message: "The answer ended unexpectedly." };
        dispatch({ type: "event", id, event });
      }
    },
    [docId, ask],
  );

  const stop = useCallback(() => {
    if (!current.current) return;
    current.current.controller.abort();
    dispatch({ type: "stopped", id: current.current.id });
  }, []);

  return { state, submit, stop };
}
