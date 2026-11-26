import type { Metadata } from "next";
import { Inter, Newsreader } from "next/font/google";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { themeInitScript } from "@/lib/theme";

import "./globals.css";

// Downloaded at build time and served by the app itself; no request to Google at runtime.
const sans = Inter({ subsets: ["latin"], variable: "--font-inter" });
const serif = Newsreader({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
});

export const metadata: Metadata = {
  title: "Research Companion",
  description: "Ask questions about a research paper and check every answer against its source.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the head script sets data-theme before React hydrates.
    <html
      lang="en"
      className={`${sans.variable} ${serif.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      {/* Browser extensions (e.g. Grammarly) add attributes to <body> before React loads. */}
      <body className="flex h-full flex-col bg-canvas text-fg" suppressHydrationWarning>
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-md bg-inverse font-serif text-base font-semibold text-on-inverse italic shadow-sm"
            >
              R
            </span>
            <span className="font-serif text-xl font-semibold tracking-tight">
              Research Companion
            </span>
          </Link>
          <span aria-hidden className="hidden h-5 w-px bg-line-strong sm:block" />
          <span className="hidden font-serif text-[15px] text-muted italic sm:inline">
            answers you can check against the paper
          </span>
          <ThemeToggle />
        </header>
        <main className="min-h-0 flex-1">{children}</main>
      </body>
    </html>
  );
}
