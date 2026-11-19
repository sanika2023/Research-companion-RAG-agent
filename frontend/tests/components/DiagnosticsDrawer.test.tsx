import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DiagnosticsDrawer } from "@/components/diagnostics/DiagnosticsDrawer";
import type { DiagnoseResponse, Signal } from "@/types/api";

function signal(overrides: Partial<Signal>): Signal {
  return {
    kind: "reorder",
    status: "ok",
    weight: 1,
    risk: 0.1,
    similarity: 0.9,
    claim_agreement: 1,
    contradictions: 0,
    question: "Which datasets?",
    answer: "TruthfulQA [3].",
    refused: false,
    ...overrides,
  };
}

const REPORT: DiagnoseResponse = {
  doc_id: "d1",
  uncertainty: 0.15,
  signals: [
    signal({ kind: "paraphrase", question: "What datasets were used?", risk: 0.05 }),
    signal({ kind: "reorder", risk: 0.13 }),
    signal({ kind: "distractor", risk: 0.26, claim_agreement: 0.75, contradictions: 1 }),
    signal({ kind: "drop_cited", weight: 0, risk: 0.21 }),
  ],
  claims: ["SelfCheckGPT used temperature 0.5.", "MetaQA was tested at 0.1-0.7."],
  flags: [],
};

function open(report: DiagnoseResponse = REPORT, onClose = vi.fn()) {
  render(<DiagnosticsDrawer question="Which temperature?" report={report} onClose={onClose} />);
  return { onClose, drawer: screen.getByRole("dialog", { name: /answer check/i }) };
}

const row = (title: string) => {
  const item = screen.getByRole("heading", { name: title }).closest("li");
  if (!item) throw new Error(`no row for ${title}`);
  return within(item);
};

describe("DiagnosticsDrawer", () => {
  it("shows the overall risk with its level and the question it checked", () => {
    const { drawer } = open();

    expect(drawer).toHaveTextContent("Which temperature?");
    expect(within(drawer).getByText("Low")).toBeInTheDocument();
    expect(within(drawer).getByText("0.15")).toBeInTheDocument();
  });

  it("says it measures consistency, not correctness", () => {
    expect(open().drawer).toHaveTextContent(/consistency, not correctness/i);
  });

  it("lists each check with its risk", () => {
    open();

    expect(row("Reworded question").getByText("risk 0.05")).toBeInTheDocument();
    expect(row("Unrelated passage added").getByText("risk 0.26")).toBeInTheDocument();
    expect(row("Unrelated passage added").getByText("1 claim contradicted.")).toBeInTheDocument();
    expect(row("Unrelated passage added").getByText(/claims agreed 75%/i)).toBeInTheDocument();
  });

  it("marks the check that is not counted in the score", () => {
    open();

    expect(
      row("Main source removed").getByText("Shown for reference; not counted in the score."),
    ).toBeInTheDocument();
  });

  it("lets the reader see the reworded question and the answer it produced", async () => {
    open();

    await userEvent.click(row("Reworded question").getByText(/show answer/i));

    expect(row("Reworded question").getByText("What datasets were used?")).toBeVisible();
    expect(row("Reworded question").getByText("TruthfulQA [3].")).toBeVisible();
  });

  it("shows skipped checks without a risk", () => {
    open({
      ...REPORT,
      signals: [signal({ kind: "distractor", status: "skipped", risk: null, answer: null })],
    });

    expect(
      row("Unrelated passage added").getByText(/skipped: every passage/i),
    ).toBeInTheDocument();
    expect(row("Unrelated passage added").queryByText(/^risk/)).toBeNull();
  });

  it("lists the claims that were compared", () => {
    open();

    expect(screen.getByText("SelfCheckGPT used temperature 0.5.")).toBeInTheDocument();
    expect(screen.getByText("MetaQA was tested at 0.1-0.7.")).toBeInTheDocument();
  });

  it("explains a score based on text similarity only", () => {
    expect(open({ ...REPORT, flags: ["judge_failed"] }).drawer).toHaveTextContent(
      /text similarity only/i,
    );
  });

  it("explains when no score could be given", () => {
    const { drawer } = open({ ...REPORT, uncertainty: null });

    expect(drawer).toHaveTextContent(/not enough checks succeeded/i);
  });

  it("moves focus into the drawer and closes from its button", async () => {
    const { onClose } = open();
    const close = screen.getByRole("button", { name: /close/i });

    expect(close).toHaveFocus();
    await userEvent.click(close);
    expect(onClose).toHaveBeenCalled();
  });
});
