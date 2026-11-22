# Evaluation summary

29 of 29 questions answered; models: answer `gemini-3.5-flash-lite`, light `gemini-3.5-flash-lite` (from .env).

## Answer correctness (answerable questions, hand-labelled)

| Correct | Partial | Wrong | Unlabelled |
| --- | --- | --- | --- |
| 17 | 5 | 2 | 0 |

## Refusals

| Unanswerable, refused | Unanswerable, answered | Answerable, refused |
| --- | --- | --- |
| 5 | 0 | 2 |

## Do the citations support the answer? (hand-labelled)

| Yes | Partly | No | Unlabelled |
| --- | --- | --- | --- |
| 20 | 2 | 0 | 0 |

## Hallucination-risk score vs. labels (first check per answer)

| Label | Answers | Mean risk |
| --- | --- | --- |
| correct | 17 | 0.06 |
| partial | 5 | 0.12 |
| wrong | 0 | n/a |

AUROC wrong vs correct: **n/a**; wrong or partial vs correct: **0.99** (0.5 = chance, 1.0 = every worse answer scored riskier).

### Per check type

| Check | AUROC strict | AUROC lenient |
| --- | --- | --- |
| paraphrase | n/a | 0.84 |
| reorder | n/a | 0.69 |
| distractor | n/a | 0.89 |
| drop_cited | n/a | 0.46 |

## Stability (same answer checked repeatedly)

| Question | Mean | Std | Low | High |
| --- | --- | --- | --- | --- |
| bb-01 | 0.07 | 0.06 | 0.04 | 0.14 |
| bb-05 | 0.07 | 0.02 | 0.06 | 0.09 |
| epi-04 | 0.11 | 0.02 | 0.10 | 0.13 |
| epi-06 | 0.12 | 0.06 | 0.05 | 0.15 |
| meta-01 | 0.11 | 0.01 | 0.11 | 0.12 |
| meta-06 | 0.12 | 0.02 | 0.10 | 0.15 |
| vggt-03 | 0.07 | 0.04 | 0.04 | 0.11 |
| vggt-04 | 0.07 | 0.05 | 0.03 | 0.13 |

0 of 8 answers changed Low/Medium/High level between runs.

### Does the separation survive re-checking? (lenient AUROC per run)

| Answers | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| 8 | 1.00 | 0.38 | 0.38 |

## Latency (seconds)

| Request | Count | Mean | Median | Max |
| --- | --- | --- | --- | --- |
| answer | 29 | 5.34 | 4.81 | 11.39 |
| check | 38 | 14.12 | 8.27 | 32.44 |

0 failed requests were recorded (retried on later runs).
