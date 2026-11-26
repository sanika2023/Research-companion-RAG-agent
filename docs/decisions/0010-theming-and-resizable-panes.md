# 0010: Light/dark theme and resizable panes

## Context
Users read long papers, often at night, and want to choose how much width goes to the PDF
versus the chat. Colours were hard-coded Tailwind palette classes (`bg-white`, `text-stone-500`)
in 14 files, and the two panes were a fixed 50/50 grid.

## Decision
- **Colours by role.** `globals.css` defines CSS variables such as `--surface`, `--muted`,
  `--line`, and `--accent` with one light and one dark value, exposed as Tailwind colours
  (`bg-surface`, `text-muted`). Components name the role, so the theme lives in one place.
  The risk badges keep explicit `dark:` variants because their colours carry meaning.
- **Theme choice:** Light, Dark, or System (follows the OS, live), cycled by a header button,
  saved in `localStorage`, and applied as `<html data-theme>`. A tiny inline script in `<head>`
  applies it before the first paint, so dark mode does not flash white on reload.
- **PDF pages stay white** on a darker backdrop: inverting a paper would distort its figures.
- **Resizable split:** a handle between the panes (drag, ←/→ in 5% steps, Home/End,
  double-click resets to 50/50), limited to 25–75% so neither pane disappears. It is a
  `role="separator"` with `aria-valuenow` for screen readers. The split is saved; narrow screens
  keep the stacked layout without a handle. The PDF already re-renders to its pane's width.
- Both preferences are read with `useSyncExternalStore` (`lib/stored.ts`), so the server
  renders the defaults and the browser switches to the saved values without hydration errors.
- No new dependencies.

## Alternatives considered
- **`dark:` variants on every class:** about twice the classes and easy to miss one.
- **Inverting the whole palette in dark mode** (redefining `stone-*`): no component changes,
  but dark text on "white" buttons would invert unpredictably.
- **`next-themes` / `react-resizable-panels`:** solid libraries, but each would be a new
  dependency for a few dozen lines of code.
- **Dark-mode PDF via a CSS invert filter:** readable text, but wrong colours in figures.
