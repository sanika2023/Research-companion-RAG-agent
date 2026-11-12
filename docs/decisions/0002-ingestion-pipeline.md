# 0002: Ingestion pipeline: parsing, chunking, embedding, storage

## Context
Uploaded PDFs must become chunks that are searchable (keyword + vector) and citable to an
exact page and region. The system must run free, locally and on small hosts.

## Decision
- **Parser:** PyMuPDF. It gives per-block text with bounding boxes and handles two-column
  layouts. Cleaning drops rotated text (arXiv watermarks) and digit-only blocks (page numbers),
  and rejoins words hyphenated across lines.
- **Chunks are page-bounded:** a sliding window of `CHUNK_SIZE` characters (default 1000) with
  `CHUNK_OVERLAP` (default 150), cut on word boundaries, never crossing a page. Every citation
  then maps to exactly one page.
- **Size in characters, not tokens:** deterministic and model-independent. 1000 characters is
  ~250 tokens, well under bge-small's 512-token limit.
- **Embeddings run locally** with fastembed (ONNX, bge-small-en-v1.5, 384-dim), in a worker
  thread so the async server stays responsive. The model is baked into the Docker image.
- **One transaction per upload:** document + chunks are flushed, the original PDF is written
  to `UPLOAD_DIR/{doc_id}.pdf`, then the transaction commits. Any failure rolls back, so there
  are never half-ingested papers. PDFs with no text layer are rejected (no OCR).
- **Ingestion is synchronous within the request** (~15–25 s per paper on a laptop CPU).

## Alternatives considered
- **Chunks spanning pages:** more context per chunk, but citations become ambiguous.
- **Token-based chunking:** a closer fit to the model's budget, but ties chunking to a tokenizer.
- **Hosted embedding API (e.g. Gemini embeddings):** faster, but adds rate limits, a network
  dependency, and makes ingestion cost money at scale.
- **Background job for ingestion** (return 202, poll status): better UX for large papers, but
  needs job state and polling. Deferred; the upload endpoint can switch later without changing
  the pipeline.
- **Storing PDFs in Postgres (bytea):** simpler to deploy, but bloats the database. Files on
  disk instead; on hosts with ephemeral disks this needs revisiting (Phase 4).
