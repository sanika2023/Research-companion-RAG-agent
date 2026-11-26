import { describe, expect, it } from "vitest";

import { clampSplit, parseSplit, splitAfterKey, splitFromPointer } from "@/lib/split";

describe("clampSplit", () => {
  it("keeps both panes between 25% and 75% wide", () => {
    expect(clampSplit(10)).toBe(25);
    expect(clampSplit(90)).toBe(75);
    expect(clampSplit(40)).toBe(40);
  });
});

describe("splitFromPointer", () => {
  it("turns the pointer position into a percentage of the container", () => {
    expect(splitFromPointer(300, { left: 100, width: 800 })).toBe(25);
    expect(splitFromPointer(600, { left: 100, width: 800 })).toBe(62.5);
  });

  it("clamps positions past the limits", () => {
    expect(splitFromPointer(0, { left: 100, width: 800 })).toBe(25);
  });
});

describe("splitAfterKey", () => {
  it("moves by 5% with the arrow keys and jumps to the limits with Home and End", () => {
    expect(splitAfterKey(50, "ArrowLeft")).toBe(45);
    expect(splitAfterKey(50, "ArrowRight")).toBe(55);
    expect(splitAfterKey(50, "Home")).toBe(25);
    expect(splitAfterKey(50, "End")).toBe(75);
    expect(splitAfterKey(73, "ArrowRight")).toBe(75);
  });

  it("ignores other keys", () => {
    expect(splitAfterKey(50, "Enter")).toBeNull();
  });
});

describe("parseSplit", () => {
  it("reads a saved split and clamps it", () => {
    expect(parseSplit("60")).toBe(60);
    expect(parseSplit("5")).toBe(25);
  });

  it("falls back to an even split for missing or invalid values", () => {
    expect(parseSplit(null)).toBe(50);
    expect(parseSplit("wide")).toBe(50);
  });
});
