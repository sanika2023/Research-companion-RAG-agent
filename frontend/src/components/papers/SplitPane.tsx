"use client";

import {
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import {
  DEFAULT_SPLIT,
  MAX_SPLIT,
  MIN_SPLIT,
  paneSplit,
  splitAfterKey,
  splitFromPointer,
} from "@/lib/split";

/**
 * Two panes side by side with a draggable handle between them (stacked, without a handle,
 * on narrow screens). The split is saved so the next paper opens the same way.
 */
export function SplitPane({ start, end }: { start: ReactNode; end: ReactNode }) {
  const saved = useSyncExternalStore(paneSplit.subscribe, paneSplit.read, paneSplit.fallback);
  // While dragging, the live position is kept here and saved once on release.
  const [dragging, setDragging] = useState<number | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const startId = useId();
  const split = dragging ?? saved;

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(split);
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (dragging === null || !container.current) return;
    setDragging(splitFromPointer(event.clientX, container.current.getBoundingClientRect()));
  };
  const onPointerUp = () => {
    if (dragging !== null) paneSplit.write(Math.round(dragging));
    setDragging(null);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = splitAfterKey(split, event.key);
    if (next === null) return;
    event.preventDefault();
    paneSplit.write(next);
  };

  return (
    <div
      ref={container}
      style={{ "--split": `${split}%` } as CSSProperties}
      className={`flex min-h-0 flex-1 flex-col lg:flex-row ${dragging !== null ? "cursor-col-resize select-none" : ""}`}
    >
      <div id={startId} className="min-h-0 min-w-0 flex-1 lg:w-(--split) lg:flex-none">
        {start}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize paper and chat"
        aria-controls={startId}
        aria-valuemin={MIN_SPLIT}
        aria-valuemax={MAX_SPLIT}
        aria-valuenow={Math.round(split)}
        tabIndex={0}
        title="Drag to resize · double-click to reset"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={onKeyDown}
        onDoubleClick={() => paneSplit.write(DEFAULT_SPLIT)}
        className="group relative hidden w-1.5 shrink-0 cursor-col-resize touch-none bg-line-strong hover:bg-accent focus-visible:bg-accent focus-visible:outline-none lg:block"
      >
        {/* A wider invisible grab area than the visible line */}
        <span aria-hidden className="absolute inset-y-0 -right-1.5 -left-1.5" />
      </div>
      <div className="min-h-0 min-w-0 flex-1">{end}</div>
    </div>
  );
}
