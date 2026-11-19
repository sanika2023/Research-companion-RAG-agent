"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { ApiError, diagnoseAnswer } from "@/lib/api";
import { askStream } from "@/lib/ask";
import { type Turn, chatReducer } from "@/lib/chat";
import { canCheck, checkRequest } from "@/lib/diagnostics";
import type { DiagnoseRequest, DiagnoseResponse, StreamEvent } from "@/types/api";

export type AskFn = (
  docId: string,
  question: string,
  options: { signal: AbortSignal },
) => AsyncIterable<StreamEvent>;

export type DiagnoseFn = (
  docId: string,
  request: DiagnoseRequest,
  options: { signal: AbortSignal },
) => Promise<DiagnoseResponse>;

/** Chat state for one paper: ask questions (one at a time), stop one, and check answers. */
export function useAsk(docId: string, ask: AskFn = askStream, diagnose: DiagnoseFn = diagnoseAnswer) {
  const [state, dispatch] = useReducer(chatReducer, { turns: [] });
  const current = useRef<{ id: string; controller: AbortController } | null>(null);
  const checks = useRef(new Set<AbortController>());
  const nextId = useRef(0);

  // Leaving the page cancels open requests, so the server stops generating.
  useEffect(() => {
    const running = checks.current;
    return () => {
      current.current?.controller.abort();
      running.forEach((controller) => controller.abort());
    };
  }, []);

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

  // On request only: a check costs several model calls on a rate-limited free tier.
  const check = useCallback(
    async (turn: Turn) => {
      if (!turn.response || !canCheck(turn.response) || turn.check.status === "checking") return;
      const controller = new AbortController();
      checks.current.add(controller);
      dispatch({ type: "check", id: turn.id, check: { status: "checking" } });
      try {
        const request = checkRequest(turn.response);
        const report = await diagnose(docId, request, { signal: controller.signal });
        dispatch({ type: "check", id: turn.id, check: { status: "done", report } });
      } catch (error) {
        if (controller.signal.aborted) return;
        const message = checkErrorMessage(error);
        dispatch({ type: "check", id: turn.id, check: { status: "error", message } });
      } finally {
        checks.current.delete(controller);
      }
    },
    [docId, diagnose],
  );

  return { state, submit, stop, check };
}

function checkErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Could not reach the server to check this answer. Please try again.";
}
