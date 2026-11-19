"use client";

import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { TurnView, checkBadgeId } from "@/components/chat/TurnView";
import { DiagnosticsDrawer } from "@/components/diagnostics/DiagnosticsDrawer";
import { type AskFn, type DiagnoseFn, useAsk } from "@/hooks/useAsk";
import { diagnoseAnswer } from "@/lib/api";
import { askStream } from "@/lib/ask";
import { isBusy } from "@/lib/chat";
import type { Citation } from "@/types/api";

type Props = {
  docId: string;
  ask?: AskFn;
  diagnose?: DiagnoseFn;
  onCite: (citation: Citation) => void;
};

export function Chat({ docId, ask = askStream, diagnose = diagnoseAnswer, onCite }: Props) {
  const { state, submit, stop, check } = useAsk(docId, ask, diagnose);
  const [openCheck, setOpenCheck] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const busy = isBusy(state);
  const bottom = useRef<HTMLDivElement>(null);

  const lastTurn = state.turns.at(-1);
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [state.turns.length, lastTurn?.streamedText, lastTurn?.phase]);

  const checked = state.turns.find((t) => t.id === openCheck);
  const closeCheck = useCallback(() => {
    // Back to the badge that opened the drawer, so keyboard users keep their place.
    if (openCheck) document.getElementById(checkBadgeId(openCheck))?.focus();
    setOpenCheck(null);
  }, [openCheck]);

  function send(event?: FormEvent) {
    event?.preventDefault();
    const question = draft.trim();
    if (!question || busy) return;
    setDraft("");
    void submit(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter adds a new line.
    if (event.key === "Enter" && !event.shiftKey) send(event);
  }

  return (
    <div className="relative flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        {state.turns.length === 0 ? (
          <p className="mt-8 text-center text-sm text-stone-500">
            Ask a question about this paper. Answers cite the passages they use; click a citation
            to see it in the PDF.
          </p>
        ) : (
          <ol className="space-y-6">
            {state.turns.map((turn) => (
              <TurnView
                key={turn.id}
                turn={turn}
                onCite={onCite}
                onCheck={() => void check(turn)}
                onOpenCheck={() => setOpenCheck(turn.id)}
              />
            ))}
          </ol>
        )}
        <div ref={bottom} />
      </div>

      <form onSubmit={send} className="flex gap-2 border-t border-stone-200 bg-white p-3">
        <textarea
          aria-label="Your question"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          maxLength={2000}
          placeholder="e.g. Which datasets were used to evaluate the method?"
          className="flex-1 resize-none rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
        />
        <div className="flex flex-col gap-1">
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded-md bg-stone-800 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-300"
          >
            Ask
          </button>
          {busy && (
            <button
              type="button"
              onClick={stop}
              className="rounded-md border border-stone-300 px-4 py-1 text-xs text-stone-600 hover:bg-stone-100"
            >
              Stop
            </button>
          )}
        </div>
      </form>

      {checked?.check.status === "done" && (
        <DiagnosticsDrawer
          question={checked.question}
          report={checked.check.report}
          onClose={closeCheck}
        />
      )}
    </div>
  );
}
