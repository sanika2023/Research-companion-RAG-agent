"use client";

import { useEffect, useSyncExternalStore } from "react";

import {
  applyTheme,
  DARK_QUERY,
  nextThemeChoice,
  themeChoice,
  type ThemeChoice,
} from "@/lib/theme";

const LABELS: Record<ThemeChoice, { icon: string; text: string }> = {
  // U+FE0E asks for the plain-text glyph; Windows otherwise draws ☀ as a colour emoji.
  light: { icon: "☀︎", text: "Light" },
  dark: { icon: "☾", text: "Dark" },
  system: { icon: "◐", text: "System" },
};

/** Header button that cycles Light → Dark → System (follow the OS). */
export function ThemeToggle() {
  const choice = useSyncExternalStore(
    themeChoice.subscribe,
    themeChoice.read,
    themeChoice.fallback,
  );

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "system") return;
    // Following the OS: switch live when the OS setting changes.
    const media = matchMedia(DARK_QUERY);
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  const { icon, text } = LABELS[choice];
  const next = LABELS[nextThemeChoice(choice)].text;
  return (
    <button
      type="button"
      onClick={() => themeChoice.write(nextThemeChoice(choice))}
      aria-label={`Theme: ${text}. Switch to ${next}`}
      title={`Theme: ${text} (click for ${next})`}
      className="ml-auto flex items-center gap-1.5 rounded-md border border-line px-2 py-1 text-xs text-muted hover:bg-subtle hover:text-fg"
    >
      <span aria-hidden className="text-sm leading-none">
        {icon}
      </span>
      <span className="hidden sm:inline">{text}</span>
    </button>
  );
}
