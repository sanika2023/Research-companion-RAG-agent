import { storedValue } from "@/lib/stored";

export type ThemeChoice = "light" | "dark" | "system";
export type Theme = "light" | "dark";

const KEY = "theme";
const NEXT: Record<ThemeChoice, ThemeChoice> = {
  light: "dark",
  dark: "system",
  system: "light",
};
export const DARK_QUERY = "(prefers-color-scheme: dark)";

export function parseThemeChoice(raw: string | null): ThemeChoice {
  return raw === "light" || raw === "dark" ? raw : "system";
}

export function nextThemeChoice(choice: ThemeChoice): ThemeChoice {
  return NEXT[choice];
}

export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): Theme {
  if (choice === "system") return systemPrefersDark ? "dark" : "light";
  return choice;
}

export const themeChoice = storedValue(KEY, parseThemeChoice);

/** Colours switch on <html data-theme>, which globals.css reads. */
export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = resolveTheme(choice, matchMedia(DARK_QUERY).matches);
}

/**
 * Runs in <head> before the page is drawn, so a dark-mode reload doesn't flash white
 * while React loads. Mirrors parseThemeChoice + resolveTheme.
 */
export const themeInitScript = `try{var c=localStorage.getItem(${JSON.stringify(KEY)});var d=c==="dark"||(c!=="light"&&matchMedia(${JSON.stringify(DARK_QUERY)}).matches);document.documentElement.dataset.theme=d?"dark":"light"}catch(e){}`;
