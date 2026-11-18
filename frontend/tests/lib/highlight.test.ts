import { describe, expect, it } from "vitest";

import { highlightBoxes } from "@/lib/highlight";

describe("highlightBoxes", () => {
  it("converts PDF-point boxes to percentages of the page", () => {
    const page = { width: 600, height: 800 };

    expect(highlightBoxes([[60, 80, 300, 160]], page)).toEqual([
      { left: "10%", top: "10%", width: "40%", height: "10%" },
    ]);
  });

  it("returns one box per text block", () => {
    const boxes = highlightBoxes(
      [
        [0, 0, 1, 1],
        [1, 1, 2, 2],
      ],
      { width: 10, height: 10 },
    );

    expect(boxes).toHaveLength(2);
  });

  it("skips malformed boxes", () => {
    expect(highlightBoxes([[1, 2, 3]], { width: 10, height: 10 })).toEqual([]);
  });
});
