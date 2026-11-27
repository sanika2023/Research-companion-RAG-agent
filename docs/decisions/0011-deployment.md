# 0011: Deployment (Vercel + Cloud Run + Neon) as a read-only demo

## Context
The thesis needs a public, free web deployment next to the `docker compose up` install. The
backend runs a local embedding model (fastembed, bge-small): it measured **222 MB** of memory at
start and **423 MB** after three searches, and uploads (parse + embed every chunk) need more.
Hosted containers lose their disk on restart, but uploaded PDFs were saved on disk
(`UPLOAD_DIR`). A public URL also means anyone can use the Gemini quota and upload files, and
the app serves the full PDF of every paper it holds.

Free tiers as checked on 2026-11-26 (they change often; re-check before relying on them):
- **Render free:** 512 MB RAM, 0.1 CPU, sleeps after 15 min idle (about 1 min to wake), no
  persistent disk.
- **Koyeb free:** 512 MB RAM, 0.1 vCPU, sleeps after 1 h idle.
- **Hugging Face Spaces:** CPU Basic is 16 GB RAM, but creating a Docker Space now appears to
  require a paid plan.
- **Google Cloud Run:** memory is configurable; per billing account each month, 180,000
  vCPU-seconds, 360,000 GiB-seconds, and 2 million requests are free (request-based billing).
  Needs a billing account.
- **Neon free:** 100 CU-hours of compute per project per month, 0.5–1 GB of storage per
  project (sources disagree), pgvector available.
- **Vercel Hobby:** free for personal, non-commercial use.

## Decision
- **Frontend on Vercel** (root directory `frontend`, `NEXT_PUBLIC_API_URL` set at build time).
- **Backend on Cloud Run** from the existing Dockerfile: 1 GiB, 1 vCPU, scales to zero, at most
  1 instance (caps usage within the free tier). The container listens on `$PORT`. Secrets
  (`DATABASE_URL`, `LLM_API_KEY`) live in Secret Manager, not in env files or the repo. A $1
  budget alert warns long before any charge.
- **Database on Neon** (direct, non-pooled connection, `sslmode=require`); the backend runs the
  migrations on boot, as in Docker.
- **PDFs stored in Postgres** (`document_files`, one row per paper, its own table so listing
  papers never loads the bytes). Uploading is one transaction, so a failure leaves nothing
  half-saved. Migration 0002 imports PDFs that older versions saved in `UPLOAD_DIR`.
- **Read-only demo:** `ALLOW_UPLOADS=false` makes `POST /documents` answer 403, and
  `GET /features` tells the frontend to replace the upload button with a short note. Papers are
  loaded by deploying with uploads on, uploading, and switching the flag off.
- **Only redistributable papers on the public demo.** The app serves the full PDF, so the
  demo uses papers whose licence allows redistribution (e.g. CC BY on arXiv). The arXiv default
  licence only lets arXiv distribute a paper.

## Alternatives considered
- **Render free / Koyeb free:** no credit card, but 512 MB leaves little room above the measured
  423 MB, and uploads would likely run out of memory.
- **Object storage (Cloud Storage, R2) for PDFs:** the usual choice at scale, but a new
  dependency and service for a handful of papers; Neon's storage is enough here.
- **Keep PDFs on disk:** the PDF viewer would break after every restart, which happens each time
  Cloud Run scales to zero.
- **Rate limiting or a password instead of turning uploads off:** more code; a free-tier Gemini
  key cannot be charged, so the remaining risk (quota running out) is acceptable for a demo.
- **Frontend on Cloud Run too:** one platform, but Vercel builds Next.js with no configuration
  and doesn't count against the Cloud Run free tier.

## Consequences
- The first request after the backend has been idle waits for a cold start (migrations check,
  then the embedding model loads on the first search).
- Cloud Run limits request bodies to 32 MB, below `MAX_UPLOAD_MB` (50); irrelevant while the
  demo has uploads off.
- Visitors still use the Gemini quota by asking questions; when it runs out, answers fail until
  it resets.
