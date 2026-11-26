import type { Metadata } from "next";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { themeInitScript } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: "Research Companion",
  description: "Ask questions about a research paper and check every answer against its source.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the head script sets data-theme before React hydrates.
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      {/* Browser extensions (e.g. Grammarly) add attributes to <body> before React loads. */}
      <body className="flex h-full flex-col bg-canvas text-fg" suppressHydrationWarning>
        <header className="flex h-12 shrink-0 items-center border-b border-line bg-surface px-4">
          <Link href="/" className="font-semibold tracking-tight">
            Research Companion
          </Link>
          <span className="ml-3 hidden text-xs text-faint sm:inline">
            answers you can check against the paper
          </span>
          <ThemeToggle />
        </header>
        <main className="min-h-0 flex-1">{children}</main>
      </body>
    </html>
  );
}
