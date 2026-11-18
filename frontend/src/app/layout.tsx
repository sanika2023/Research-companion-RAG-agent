import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Paper RAG",
  description: "Ask questions about a research paper and check every answer against its source.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full flex-col bg-stone-50 text-stone-900">
        <header className="flex h-12 shrink-0 items-center border-b border-stone-200 bg-white px-4">
          <Link href="/" className="font-semibold tracking-tight">
            Paper RAG
          </Link>
          <span className="ml-3 hidden text-xs text-stone-500 sm:inline">
            answers you can check against the paper
          </span>
        </header>
        <main className="min-h-0 flex-1">{children}</main>
      </body>
    </html>
  );
}
