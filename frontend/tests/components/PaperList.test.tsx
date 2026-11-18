import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PaperList } from "@/components/papers/PaperList";

describe("PaperList", () => {
  it("links each paper to its page", () => {
    render(
      <PaperList
        papers={[
          {
            doc_id: "d1",
            filename: "metaqa.pdf",
            page_count: 14,
            chunk_count: 94,
            created_at: "2026-11-12T10:00:00Z",
          },
        ]}
      />,
    );

    const link = screen.getByRole("link", { name: /metaqa\.pdf/i });
    expect(link).toHaveAttribute("href", "/papers/d1");
    expect(link).toHaveTextContent("14 pages");
  });

  it("explains what to do when there are no papers", () => {
    render(<PaperList papers={[]} />);

    expect(screen.getByText(/no papers yet/i)).toBeInTheDocument();
  });
});
