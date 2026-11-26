import { storedValue } from "@/lib/stored";

// Percent of the width given to the first (PDF) pane; limits keep both panes usable.
export const MIN_SPLIT = 25;
export const MAX_SPLIT = 75;
export const DEFAULT_SPLIT = 50;
const KEY_STEP = 5;

export function clampSplit(percent: number): number {
  return Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, percent));
}

export function splitFromPointer(x: number, box: { left: number; width: number }): number {
  return clampSplit(((x - box.left) / box.width) * 100);
}

/** New split after a key press on the handle, or null for keys it doesn't use. */
export function splitAfterKey(current: number, key: string): number | null {
  switch (key) {
    case "ArrowLeft":
      return clampSplit(current - KEY_STEP);
    case "ArrowRight":
      return clampSplit(current + KEY_STEP);
    case "Home":
      return MIN_SPLIT;
    case "End":
      return MAX_SPLIT;
    default:
      return null;
  }
}

export function parseSplit(raw: string | null): number {
  const value = Number(raw);
  return raw === null || raw === "" || Number.isNaN(value) ? DEFAULT_SPLIT : clampSplit(value);
}

export const paneSplit = storedValue("paneSplit", parseSplit);
