import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnswerText } from "@/components/chat/AnswerText";

describe("AnswerText", () => {
  it("renders Markdown formatting", () => {
    render(<AnswerText text="Uses **TruthfulQA**." citedNumbers={null} onCite={() => {}} />);

    expect(screen.getByText("TruthfulQA").tagName).toBe("STRONG");
  });

  it("turns citation markers into buttons that report the number", async () => {
    const onCite = vi.fn();
    render(<AnswerText text="A [1] and B [2, 3]." citedNumbers={[1, 2, 3]} onCite={onCite} />);

    await userEvent.click(screen.getByRole("button", { name: "Citation 3" }));

    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(onCite).toHaveBeenCalledWith(3);
  });

  it("handles adjacent markers like [1][2]", () => {
    render(<AnswerText text="A [1][2]." citedNumbers={[1, 2]} onCite={() => {}} />);

    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("shows markers as plain text while the answer is still streaming", () => {
    render(<AnswerText text="A [1]" citedNumbers={null} onCite={() => {}} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument();
  });

  it("does not make buttons out of numbers that are not citations", () => {
    render(<AnswerText text="In [2021] work [1]." citedNumbers={[1]} onCite={() => {}} />);

    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText(/\[2021\]/)).toBeInTheDocument();
  });
});
