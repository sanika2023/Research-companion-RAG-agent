import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Sources } from "@/components/citations/Sources";
import type { Citation } from "@/types/api";

const CITATIONS: Citation[] = [
  { number: 1, chunk_id: "c1", page: 9, text: "MetaQA is evaluated on TruthfulQA.", bbox: [] },
  { number: 2, chunk_id: "c2", page: 3, text: "Other passage.", bbox: [] },
];

describe("Sources", () => {
  it("lists each citation with its page", () => {
    render(<Sources citations={CITATIONS} onCite={() => {}} />);

    expect(screen.getByRole("button", { name: /\[1\].*page 9/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\[2\].*page 3/i })).toBeInTheDocument();
  });

  it("jumps to a citation when it is clicked", async () => {
    const onCite = vi.fn();
    render(<Sources citations={CITATIONS} onCite={onCite} />);

    await userEvent.click(screen.getByRole("button", { name: /page 9/i }));

    expect(onCite).toHaveBeenCalledWith(CITATIONS[0]);
  });

  it("can expand a citation to read the quoted passage", async () => {
    render(<Sources citations={CITATIONS} onCite={() => {}} />);
    const [firstToggle] = screen.getAllByText(/show passage/i);

    await userEvent.click(firstToggle!);

    expect(screen.getByText("MetaQA is evaluated on TruthfulQA.")).toBeVisible();
  });

  it("renders nothing without citations", () => {
    const { container } = render(<Sources citations={[]} onCite={() => {}} />);

    expect(container).toBeEmptyDOMElement();
  });
});
