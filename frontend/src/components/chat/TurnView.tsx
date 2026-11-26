import { AnswerText } from "@/components/chat/AnswerText";
import { Sources } from "@/components/citations/Sources";
import { CheckAnswer } from "@/components/diagnostics/CheckAnswer";
import { type Turn, visibleAnswer } from "@/lib/chat";
import { canCheck } from "@/lib/diagnostics";
import type { Citation, Step } from "@/types/api";

const STEP_LABELS: Record<Step, string> = {
  classify: "Understanding the question",
  decompose: "Breaking the question into parts",
  retrieve: "Searching the paper",
  synthesize: "Writing the answer",
};

// Audit flags from the backend that the reader should know about.
const FLAG_NOTES: Record<string, string> = {
  uncited: "This answer cites no passages. Check it against the paper.",
  invalid_citations_removed: "Some citations pointed to nothing and were removed.",
};

type Props = {
  turn: Turn;
  onCite: (citation: Citation) => void;
  onCheck: () => void;
  onOpenCheck: () => void;
};

/** Id of a turn's risk badge, so focus can return to it when the drawer closes. */
export const checkBadgeId = (turnId: string) => `check-${turnId}`;

export function TurnView({ turn, onCite, onCheck, onOpenCheck }: Props) {
  const text = visibleAnswer(turn);
  const response = turn.response;
  const citeByNumber = (number: number) => {
    const citation = response?.citations.find((c) => c.number === number);
    if (citation) onCite(citation);
  };

  return (
    <li className="space-y-2">
      <p className="ml-auto w-fit max-w-[85%] rounded-lg bg-inverse px-3 py-2 text-sm text-on-inverse">
        {turn.question}
      </p>

      <div className="rounded-lg border border-line bg-surface px-3 py-2">
        {turn.phase === "working" && !text && (
          <p className="flex items-center gap-2 text-sm text-faint">
            <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden />
            {STEP_LABELS[turn.step ?? "classify"]}…
          </p>
        )}

        {turn.subQuestions.length > 0 && (
          <div className="mb-2 text-xs text-faint">
            Looked into:
            <ul className="ml-4 list-disc">
              {turn.subQuestions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {response?.refused ? (
          <p role="note" className="text-sm text-muted italic">
            {response.answer}
          </p>
        ) : (
          text && (
            <AnswerText
              text={text}
              citedNumbers={response ? response.citations.map((c) => c.number) : null}
              onCite={citeByNumber}
            />
          )
        )}

        {response?.flags
          .filter((flag) => flag in FLAG_NOTES)
          .map((flag) => (
            <p key={flag} className="mt-2 text-xs text-warn">
              ⚠ {FLAG_NOTES[flag]}
            </p>
          ))}

        {turn.phase === "error" && (
          <p role="alert" className="mt-1 text-sm text-danger">
            {turn.error}
          </p>
        )}
        {turn.phase === "stopped" && <p className="mt-1 text-xs text-faint">Stopped.</p>}

        {response && <Sources citations={response.citations} onCite={onCite} />}

        {turn.phase === "done" && response && canCheck(response) && (
          <CheckAnswer
            check={turn.check}
            badgeId={checkBadgeId(turn.id)}
            onCheck={onCheck}
            onOpen={onOpenCheck}
          />
        )}
      </div>
    </li>
  );
}
