import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UploadForm } from "@/components/papers/UploadForm";
import { ApiError } from "@/lib/api";
import type { DocumentUploaded } from "@/types/api";

const FILE = new File(["%PDF-"], "paper.pdf", { type: "application/pdf" });
const UPLOADED: DocumentUploaded = {
  doc_id: "d1",
  filename: "paper.pdf",
  page_count: 3,
  chunk_count: 9,
};

describe("UploadForm", () => {
  it("uploads the chosen PDF and reports the new paper", async () => {
    const upload = vi.fn(async () => UPLOADED);
    const onUploaded = vi.fn();
    render(<UploadForm upload={upload} onUploaded={onUploaded} />);

    await userEvent.upload(screen.getByLabelText(/upload a paper/i), FILE);

    expect(upload).toHaveBeenCalledWith(FILE);
    expect(onUploaded).toHaveBeenCalledWith(UPLOADED);
  });

  it("shows that the paper is being processed", async () => {
    const upload = vi.fn(() => new Promise<DocumentUploaded>(() => {}));
    render(<UploadForm upload={upload} onUploaded={() => {}} />);

    await userEvent.upload(screen.getByLabelText(/upload a paper/i), FILE);

    expect(await screen.findByText(/processing paper\.pdf/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/upload a paper/i)).toBeDisabled();
  });

  it("shows the server's reason when an upload is rejected", async () => {
    const upload = vi.fn(async (): Promise<DocumentUploaded> => {
      throw new ApiError(400, "PDF has no extractable text");
    });
    render(<UploadForm upload={upload} onUploaded={() => {}} />);

    await userEvent.upload(screen.getByLabelText(/upload a paper/i), FILE);

    expect(await screen.findByRole("alert")).toHaveTextContent("PDF has no extractable text");
    expect(screen.getByLabelText(/upload a paper/i)).toBeEnabled();
  });
});
