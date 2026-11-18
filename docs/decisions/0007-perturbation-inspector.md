# 0007: Perturbation inspector

## Context
Citations show *where* an answer came from, but not whether the model actually relied on the
passages or would say the same thing again. We want a per-answer hallucination-risk score
that needs no labelled data or model internals (Gemini is a black box), costs little on the
free tier, and explains itself.

## Decision
- **Consistency under controlled change.** Re-run the answer step with one input changed at a
  time and measure how far the answer moves:
  - `paraphrase`: the question reworded by Flash-Lite, passages unchanged;
  - `reorder`: the same passages in reverse order;
  - `distractor`: an unretrieved passage of the same paper added first (seeded by the question,
    so re-inspection is repeatable);
  - `drop_cited`: the passage the answer cites most removed.
  Retrieval is not re-run, so each signal isolates one cause.
- **Two comparison signals per run:** cosine similarity of bge embeddings (citation markers
  stripped, rescaled so `DIAGNOSTICS_SIMILARITY_FLOOR`=0.7 maps to 0), and claim agreement
  from one batched Flash-Lite "judge" call that splits the original into claims and marks each
  as agrees / contradicts / missing in every perturbed answer. A perturbed refusal counts as
  zero agreement without being judged.
- **Score:** each run's agreement is the mean of its available signals; its risk is
  `1 - agreement`, except `drop_cited`, where an *unchanged* answer is the risk. The
  uncertainty is the weighted mean of the risks.
- **`drop_cited` is reported but weighted 0 by default.** Papers repeat key facts (abstract,
  introduction, conclusion), so an unchanged answer often means redundant evidence, not
  memorised knowledge. Evaluation will show whether it predicts wrong answers.
- **Graceful degradation:** a failed run is reported as `failed` and left out; if the judge
  fails, the score falls back to embedding similarity (`judge_failed` flag); only when every
  run fails is it a 503.
- **Delivery:** a separate `POST /documents/{doc_id}/diagnose` that the client calls after the
  answer is shown. `/ask` and the `done` event now include `passage_ids` (every passage the
  model saw, in order) so the inspector can rebuild the exact prompt. Stateless: no new table.
- **Cost:** ~6 light-model calls (1 paraphrase, up to 4 answers, 1 judge), at most
  `DIAGNOSTICS_CONCURRENCY`=2 at once to respect free-tier rate limits.

## Alternatives considered
- **Token log-probabilities / self-reported confidence:** not available or not reliable for
  Gemini through the free API; perturbation works with any black-box model.
- **Sampling the same prompt N times (SelfCheckGPT-style):** measures randomness only; our
  perturbations also test sensitivity to wording, order, and noise, and say which one failed.
- **Continuing the SSE stream with a `diagnostics` event:** keeps one connection, but holds
  it open 5-20 s after the answer and couples the two features; a separate call is simpler to
  test, retry, and use from the evaluation scripts.
- **Background task + database table + polling:** survives page reloads, but adds a
  migration, job state, and cleanup for no benefit while the client waits anyway.
- **Paraphrase with re-retrieval:** more end-to-end, but mixes retrieval changes with model
  sensitivity in a single signal.
- **Embedding similarity only:** free and fast, but formatting changes move it a lot (see
  report notes); claim agreement measures meaning.
