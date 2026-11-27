import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DemoNote } from "@/components/papers/DemoNote";
import type { PaperCredit } from "@/lib/demo-papers";

const credit: PaperCredit = {
  title: "A Paper About Uncertainty",
  authors: "Ada Lovelace, Alan Turing",
  arxivId: "2401.00001",
  licence: "CC BY 4.0",
  licenceUrl: "https://creativecommons.org/licenses/by/4.0/",
};

describe("DemoNote", () => {
  it("says this is a demo with uploads turned off", () => {
    render(<DemoNote credits={[credit]} />);

    expect(screen.getByText(/demo mode/i)).toBeInTheDocument();
    expect(screen.getByText(/uploads turned off/i)).toBeInTheDocument();
  });

  it("credits each paper with its authors, source link, and licence link", () => {
    render(<DemoNote credits={[credit]} />);

    const item = screen.getByRole("listitem");
    expect(within(item).getByText(/ada lovelace, alan turing/i)).toBeInTheDocument();
    expect(within(item).getByRole("link", { name: /a paper about uncertainty/i })).toHaveAttribute(
      "href",
      "https://arxiv.org/abs/2401.00001",
    );
    expect(within(item).getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by/4.0/",
    );
  });

  it("opens credit links in a new tab so visitors keep their place", () => {
    render(<DemoNote credits={[credit]} />);

    for (const link of screen.getAllByRole("link")) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noreferrer");
    }
  });
});
