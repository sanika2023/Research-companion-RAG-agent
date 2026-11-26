import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/theme/ThemeToggle";

function prefersDark(dark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: dark,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    prefersDark(true);
  });

  it("follows the system theme until a choice is made", () => {
    render(<ThemeToggle />);

    expect(screen.getByRole("button", { name: /theme: system/i })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("cycles light, dark, system and remembers the choice", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /theme/i });

    fireEvent.click(button);
    expect(button).toHaveAccessibleName(/theme: light/i);
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("theme")).toBe("light");

    fireEvent.click(button);
    expect(button).toHaveAccessibleName(/theme: dark/i);
    expect(document.documentElement.dataset.theme).toBe("dark");

    fireEvent.click(button);
    expect(button).toHaveAccessibleName(/theme: system/i);
  });

  it("starts from a saved choice", () => {
    localStorage.setItem("theme", "light");

    render(<ThemeToggle />);

    expect(screen.getByRole("button", { name: /theme: light/i })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
