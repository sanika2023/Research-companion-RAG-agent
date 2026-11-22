# 0009: Evaluation method

## Context
The thesis needs evidence for three claims: retrieval finds the right pages, answers are
correct and cited, and the hallucination-risk score warns about worse answers. Gemini's free
tier limits how many model calls a run can make, and runs can stop part-way (busy model,
quota). With only a few dozen questions, results must be reproducible and honest about noise.

## Decision
- **Question set** (`eval/queries/queries.jsonl`): 29 questions over the 4 sample papers,
  24 answerable plus 5 the paper cannot answer, each with expected pages and a reference answer.
  Each question is stored in a user's wording (used for answers) and the paper's wording, so
  the effect of vocabulary on retrieval can be measured.
- **Retrieval** is compared without model calls by running keyword, vector, and hybrid search
  with the app's own search functions; a hit is a passage from an expected page in the top k.
- **Answers** come from the running backend's real `/ask` and `/diagnose` endpoints, so the
  evaluation measures what users get, including latency. Results are saved after every request
  and the run resumes where it stopped; repeated checks of the same answers measure stability.
- **Correctness is labelled by hand** (correct / partial / wrong, plus citation support) in a
  CSV that hides the risk score, so the score cannot sway the labels. Regenerating the sheet
  keeps existing labels and flags any answer that changed.
- **Score quality** is AUROC of the first check (what a user sees), strict (wrong vs correct)
  and lenient (wrong or partial vs correct), per check type, and per repeated run.
- The scripts live in `backend/app/evaluation/` and run with `python -m`, with pure, tested
  helpers (`metrics`, `queries`, `answers`, `labels`, `summary`).

## Alternatives considered
- **LLM-as-judge labels:** faster, but the risk score itself uses an LLM judge, so the two would
  share blind spots and inflate agreement.
- **An evaluation framework (e.g. RAGAS):** would add a dependency and relies on LLM judging.
- **Calling the agent in-process:** no server needed, but it would duplicate the routes' wiring
  and skip the API layer users go through.
- **Scripts in `eval/scripts/`:** the backend is not an installed package, so they would need
  `sys.path` workarounds to import the app.
- **Reporting the first check only:** simpler, but on this data it would have reported an
  AUROC of 0.99 that re-checks did not reproduce (0.38).
