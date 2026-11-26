import { describe, expect, it } from "vitest";

import { nextThemeChoice, parseThemeChoice, resolveTheme } from "@/lib/theme";

describe("parseThemeChoice", () => {
  it("keeps a saved choice", () => {
    expect(parseThemeChoice("dark")).toBe("dark");
    expect(parseThemeChoice("light")).toBe("light");
  });

  it("falls back to following the system for missing or unknown values", () => {
    expect(parseThemeChoice(null)).toBe("system");
    expect(parseThemeChoice("purple")).toBe("system");
  });
});

describe("nextThemeChoice", () => {
  it("cycles light, dark, system", () => {
    expect(nextThemeChoice("light")).toBe("dark");
    expect(nextThemeChoice("dark")).toBe("system");
    expect(nextThemeChoice("system")).toBe("light");
  });
});

describe("resolveTheme", () => {
  it("follows the operating system only when the choice is system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});
