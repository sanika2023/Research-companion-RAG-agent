import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";
import { getFeatures, listDocuments } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", () => ({
  listDocuments: vi.fn(),
  getFeatures: vi.fn(),
  uploadDocument: vi.fn(),
}));

describe("HomePage", () => {
  beforeEach(() => {
    vi.mocked(listDocuments).mockResolvedValue([]);
  });

  it("offers uploads when the server allows them", async () => {
    vi.mocked(getFeatures).mockResolvedValue({ uploads_enabled: true });

    render(<HomePage />);

    expect(await screen.findByText(/upload a paper/i)).toBeInTheDocument();
  });

  it("explains the demo instead of offering uploads when they are turned off", async () => {
    vi.mocked(getFeatures).mockResolvedValue({ uploads_enabled: false });

    render(<HomePage />);

    expect(await screen.findByText(/this demo/i)).toBeInTheDocument();
    expect(screen.queryByText(/upload a paper/i)).not.toBeInTheDocument();
  });

  it("credits the demo papers only when uploads are turned off", async () => {
    vi.mocked(getFeatures).mockResolvedValue({ uploads_enabled: false });

    render(<HomePage />);

    expect(await screen.findByText(/paper credits/i)).toBeInTheDocument();
  });

  it("shows no demo credits when uploads are on", async () => {
    vi.mocked(getFeatures).mockResolvedValue({ uploads_enabled: true });

    render(<HomePage />);

    await screen.findByText(/upload a paper/i);
    expect(screen.queryByText(/paper credits/i)).not.toBeInTheDocument();
  });
});
