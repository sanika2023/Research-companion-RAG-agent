# 0008: Diagnostics drawer (answer check UI)

## Context
The perturbation inspector (ADR 0007) costs about six Flash-Lite calls and 5-20 seconds per
answer. The Gemini free tier has per-minute and per-day request limits that the chat, the
inspector, and the evaluation all share. Readers need the score at a glance, plus enough
detail to judge it themselves rather than trust a single number.

## Decision
- **On request:** each finished, non-refused answer gets a "Check this answer" button; nothing
  runs automatically. Refusals and answers without passages get no button.
- **Badge, then drawer:** the result is a coloured badge under the answer ("Hallucination
  risk: Low · 0.14"); clicking it opens a side drawer over the chat (the PDF stays visible)
  with the overall score, a plain-language explanation that it measures consistency, not
  correctness, one row per check (risk, similarity, claim agreement, notes, and the perturbed
  answer behind "Show answer"), and the claims compared.
- **Levels:** Low < 0.2, Medium < 0.4, High otherwise; the number is always shown. These are
  placeholders from a handful of real answers, kept in one constant to recalibrate in the
  evaluation.
- **State:** the check lives on the chat turn (`idle → checking → done | error`) in the same
  reducer as the answer; a check may update a turn after it is final. Checks don't block
  asking the next question and are cancelled when the page closes.
- **Accessibility:** the drawer is a labelled `role="dialog"`; focus moves to its close button,
  Escape or the backdrop closes it, and focus returns to the badge.
- Perturbed answers are shown as plain text: their `[n]` numbers refer to reshuffled passages,
  so they are not linked to the PDF.

## Alternatives considered
- **Automatic check after every answer:** matches "scores each answer" but would roughly
  triple model calls per question and exhaust the free tier during evaluation.
- **Inline expandable panel under the answer:** simpler, but a long breakdown pushes the
  conversation away; the drawer keeps both answer and breakdown in view.
- **Native `<dialog>`:** less code, but jsdom (used by the tests) does not implement
  `showModal`, so behaviour could not be tested the same way.
- **Hide the number, show only the level:** friendlier, but hides how close a score is to a
  cut-off that is not yet calibrated.
