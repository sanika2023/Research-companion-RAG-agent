# 0004: Question-answering agent and citation checking

## Context
Answers must be grounded in the selected paper and every claim must cite a page. The LLM is
Gemini on the free tier: rate-limited, sometimes overloaded, and occasionally slow.

## Decision
- **LangGraph state machine:** `classify → [decompose if multi-step] → retrieve → synthesize →
  check_citations`, with `retrieve → refuse` when nothing is found. One file per node; nodes
  read and return parts of a shared typed state, so each is unit-testable alone.
- **Two model tiers:** Flash-Lite ("light") for classify/decompose (cheap routing),
  Flash ("answer") for the final answer. Names come from env vars.
- **Structured output** (Gemini JSON-schema mode, validated with Pydantic) for routing steps,
  rather than parsing free text.
- **Numbered passages, `[n]` citations:** retrieved chunks are shown to the model as
  `[n] (page p)`; the model must cite `[n]` and reply `NOT_FOUND` if the passages don't answer.
- **Citations are verified in code, not trusted:** markers pointing to passages the model
  was never shown are removed and flagged; an answer with no valid citation is flagged
  `uncited`. Every citation maps to a chunk id, page, and bbox for the viewer.
- **Refuse rather than guess:** no passages → no model call; the agent says it couldn't find
  the answer in this paper.
- **Graceful degradation:** if classify/decompose fail, the agent continues on the simple
  path and records a flag. If the answer model is unavailable, the API returns 503.
- **Resilience:** retry 429/500/503 with exponential backoff (2 s, 4 s, 8 s); a per-request
  timeout (60 s) sent to Google as a deadline; 504 (deadline passed) is not retried.
- **Prompt-injection hygiene:** passages are wrapped in `<passages>` and the prompt states
  they are data, not instructions.
- **Single-turn:** each question is answered independently (no conversation memory).

## Alternatives considered
- **Plain function pipeline (no LangGraph):** simpler today, but the perturbation `diagnose`
  step and future tool calls fit naturally as graph nodes.
- **Always decompose:** more model calls for questions that don't need it.
- **Trusting model citations:** models occasionally cite passages that don't exist; checking
  is cheap and deterministic.
- **One model for everything:** simpler, but the stronger model's free-tier quota is smaller;
  routing calls don't need it.
