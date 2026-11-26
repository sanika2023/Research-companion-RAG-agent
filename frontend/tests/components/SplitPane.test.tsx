import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { SplitPane } from "@/components/papers/SplitPane";

function renderPanes() {
  render(<SplitPane start={<p>paper</p>} end={<p>chat</p>} />);
  return screen.getByRole("separator", { name: /resize/i });
}

describe("SplitPane", () => {
  beforeEach(() => localStorage.clear());

  it("shows both panes with an even split by default", () => {
    const handle = renderPanes();

    expect(screen.getByText("paper")).toBeInTheDocument();
    expect(screen.getByText("chat")).toBeInTheDocument();
    expect(handle).toHaveAttribute("aria-valuenow", "50");
  });

  it("moves with the arrow keys and remembers the split", () => {
    const handle = renderPanes();

    fireEvent.keyDown(handle, { key: "ArrowRight" });

    expect(handle).toHaveAttribute("aria-valuenow", "55");
    expect(localStorage.getItem("paneSplit")).toBe("55");
  });

  it("resets to an even split on double-click", () => {
    const handle = renderPanes();
    fireEvent.keyDown(handle, { key: "Home" });

    fireEvent.doubleClick(handle);

    expect(handle).toHaveAttribute("aria-valuenow", "50");
  });

  it("starts from a saved split", () => {
    localStorage.setItem("paneSplit", "65");

    expect(renderPanes()).toHaveAttribute("aria-valuenow", "65");
  });
});
