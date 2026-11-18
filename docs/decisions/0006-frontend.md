# 0006: Frontend architecture

## Context
The app needs a dual-pane UI: a PDF viewer and a chat that streams answers, where clicking a
citation shows the exact cited passage. The backend is a separate service (FastAPI) and will be
hosted separately from the frontend (Vercel) when deployed.

## Decision
- **Next.js 16 (App Router) + TypeScript (strict, `noUncheckedIndexedAccess`) + Tailwind 4.**
  All data fetching happens in the browser; the paper page is a client component inside a
  `<Suspense>` boundary (Next 16 prerenders everything else at build time).
- **The browser calls the API directly, with CORS** (`CORS_ORIGINS` on the backend), rather
  than proxying through Next.js: a proxy can buffer Server-Sent Events, and direct calls keep the
  frontend and backend independently deployable. `NEXT_PUBLIC_API_URL` is a build-time setting.
- **Streaming via `fetch` + our own SSE parser,** because `EventSource` cannot POST. The parser
  is a pure, tested class that copes with events split anywhere across network chunks.
  `askStream` turns every failure (HTTP error, network error, dropped stream) into one final
  `error` event.
- **Chat state is a pure reducer** (`asked` → `working` → `done` / `error` / `stopped`); finished
  turns ignore late events. The streamed text is replaced by the citation-checked answer on
  `done` (ADR 0005). Citation markers only become buttons once verified.
- **`react-pdf` (pdf.js) for the viewer,** rendered only in the browser, with its worker bundled
  (no CDN). Highlights are drawn from the chunk bounding boxes as **percentages of the page
  size**, so they stay aligned at any width.
- **`react-markdown`** renders answers (bold, lists) without raw HTML; `[n]` markers are rewritten
  to `#cite-n` links and rendered as buttons.
- Components receive their side-effecting functions (`ask`, `upload`) as props, so tests pass
  fakes instead of mocking modules.

## Alternatives considered
- **Browser's built-in PDF viewer (`<iframe>`):** no dependency, but no passage highlighting
  and unreliable page jumps after load.
- **Proxying the API through Next.js rewrites:** no CORS, but SSE may be buffered and the
  frontend host would carry every API request.
- **WebSockets / EventSource:** see ADR 0005.
- **Rendering math (KaTeX):** two more packages; deferred, LaTeX shows as raw text.
