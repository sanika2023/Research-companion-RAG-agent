"use client";

import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";

import { highlightBoxes, type PageSize } from "@/lib/highlight";

// Bundled with the app (not a CDN) so it works offline and its version matches react-pdf's.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

/** A passage to show: `id` changes on every click, so re-clicking the same citation scrolls again. */
export type PdfTarget = { page: number; bbox: number[][]; id: number };

type Props = { url: string; target: PdfTarget | null };

const LETTER_RATIO = 11 / 8.5; // placeholder height until a page's real size is known

export function PdfViewer({ url, target }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const firstHighlight = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [pageCount, setPageCount] = useState(0);
  const [sizes, setSizes] = useState<Record<number, PageSize>>({});

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.floor(entry.contentRect.width) - 32); // minus padding
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Scroll once the target page has loaded (before that, its height and highlight are unknown).
  const targetLoaded = target ? sizes[target.page] !== undefined : false;
  useEffect(() => {
    if (target && targetLoaded) {
      firstHighlight.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [target, targetLoaded]);

  return (
    <div ref={container} className="h-full overflow-y-auto bg-sunken p-4">
      <Document
        file={url}
        onLoadSuccess={(pdf) => setPageCount(pdf.numPages)}
        loading={<p className="text-sm text-muted">Loading PDF…</p>}
        error={
          <p role="alert" className="text-sm text-danger">
            Could not load this paper&apos;s PDF.
          </p>
        }
      >
        {width > 0 &&
          Array.from({ length: pageCount }, (_, i) => i + 1).map((number) => {
            const size = sizes[number];
            const boxes = target?.page === number && size ? highlightBoxes(target.bbox, size) : [];
            return (
              <div
                key={number}
                className="relative mx-auto mb-4 bg-[white] shadow"
                style={{ width, minHeight: size ? undefined : width * LETTER_RATIO }}
                aria-label={`Page ${number}`}
              >
                <Page
                  pageNumber={number}
                  width={width}
                  renderAnnotationLayer={false}
                  onLoadSuccess={(page) =>
                    setSizes((s) => ({
                      ...s,
                      [number]: { width: page.originalWidth, height: page.originalHeight },
                    }))
                  }
                />
                {boxes.map((box, i) => (
                  <div
                    key={`${target?.id}-${i}`}
                    ref={i === 0 ? firstHighlight : undefined}
                    className="pointer-events-none absolute rounded-sm bg-amber-300/40 ring-2 ring-amber-500/70"
                    style={box}
                  />
                ))}
              </div>
            );
          })}
      </Document>
    </div>
  );
}
