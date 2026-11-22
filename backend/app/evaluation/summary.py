"""Turn answer-run results and hand labels into the report's tables.

Run from backend/ after labelling:  uv run python -m app.evaluation.summary
"""

import statistics
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from app.core.config import get_settings
from app.evaluation.answers import AnswerRecord, load_records
from app.evaluation.labels import read_labels
from app.evaluation.metrics import Spread, auroc, refusal_counts, spread
from app.evaluation.queries import Query, load_queries
from app.evaluation.report import table
from app.schemas.diagnose import DiagnoseResponse

SUMMARY_PATH = Path("../eval/results/summary.md")
LABELS = ("correct", "partial", "wrong")
SIGNALS = ("paraphrase", "reorder", "distractor", "drop_cited")
# Same cut-offs as the UI badge (frontend/src/lib/diagnostics.ts).
LEVEL_CUTS = (0.2, 0.4)

ByLabel = dict[str, list[float]]


def labelled_risks(
    queries: Sequence[Query], records: Mapping[str, AnswerRecord], labels: Mapping[str, str]
) -> ByLabel:
    """Overall risk of each labelled, answerable answer, grouped by its label."""
    return _group(queries, records, labels, lambda report: report.uncertainty)


def signal_risks(
    queries: Sequence[Query],
    records: Mapping[str, AnswerRecord],
    labels: Mapping[str, str],
    *,
    kind: str,
) -> ByLabel:
    """Like labelled_risks, but for one check type's risk alone."""

    def risk_of(report: DiagnoseResponse) -> float | None:
        return next((s.risk for s in report.signals if s.kind == kind), None)

    return _group(queries, records, labels, risk_of)


def stability(records: Mapping[str, AnswerRecord]) -> list[tuple[str, Spread]]:
    """Spread of the overall risk for answers checked more than once."""
    rows = []
    for qid, record in records.items():
        scores = [c.report.uncertainty for c in record.checks if c.report.uncertainty is not None]
        if len(scores) > 1:
            rows.append((qid, spread(scores)))
    return rows


def per_run_separation(
    queries: Sequence[Query],
    records: Mapping[str, AnswerRecord],
    labels: Mapping[str, str],
    *,
    runs: int,
) -> list[float | None]:
    """Lenient AUROC of each repeated check, on the answers that have all `runs` checks.

    Shows whether the first check's separation survives re-running the same answers.
    """
    repeated = {qid: r for qid, r in records.items() if len(r.checks) >= runs}
    return [
        _separation(_group(queries, repeated, labels, lambda rep: rep.uncertainty, run=run))[1]
        for run in range(runs)
    ]


def _group(
    queries: Sequence[Query],
    records: Mapping[str, AnswerRecord],
    labels: Mapping[str, str],
    score_of: Callable[[DiagnoseResponse], float | None],
    *,
    run: int = 0,  # the first check is what a user would have seen
) -> ByLabel:
    groups: ByLabel = {}
    for query in queries:
        record, label = records.get(query.id), labels.get(query.id, "")
        if not query.answerable or label not in LABELS or record is None:
            continue
        if len(record.checks) <= run:
            continue
        score = score_of(record.checks[run].report)
        if score is not None:
            groups.setdefault(label, []).append(score)
    return groups


def _separation(groups: ByLabel) -> tuple[float | None, float | None]:
    """AUROC for wrong vs correct (strict) and wrong-or-partial vs correct (lenient)."""
    right, wrong, partial = (groups.get(k, []) for k in ("correct", "wrong", "partial"))
    return auroc(wrong=wrong, right=right), auroc(wrong=wrong + partial, right=right)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _level(score: float) -> int:
    return sum(score >= cut for cut in LEVEL_CUTS)


def main() -> None:
    queries, records = load_queries(), load_records()
    label_rows = read_labels()
    labels = {qid: row.get("correctness", "").strip().lower() for qid, row in label_rows.items()}
    support = {
        qid: row.get("citations_support", "").strip().lower() for qid, row in label_rows.items()
    }
    # (query, answer) for every question that got an answer
    answered = [(q, r.answer) for q in queries if (r := records.get(q.id)) and r.answer]
    settings = get_settings()
    out = [
        "# Evaluation summary",
        f"{len(answered)} of {len(queries)} questions answered; models: answer "
        f"`{settings.llm_answer_model}`, light `{settings.llm_light_model}` (from .env).",
    ]

    answerable = [(q, a) for q, a in answered if q.answerable]
    counts = [sum(labels.get(q.id) == label for q, _ in answerable) for label in LABELS]
    unlabelled = len(answerable) - sum(counts)
    out += [
        "## Answer correctness (answerable questions, hand-labelled)",
        table(
            ["Correct", "Partial", "Wrong", "Unlabelled"], [[*map(str, counts), str(unlabelled)]]
        ),
    ]

    refusals = refusal_counts((q.answerable, a.refused) for q, a in answered)
    out += [
        "## Refusals",
        table(
            ["Unanswerable, refused", "Unanswerable, answered", "Answerable, refused"],
            [
                [
                    str(refusals.correct_refusals),
                    str(refusals.missed_refusals),
                    str(refusals.false_refusals),
                ]
            ],
        ),
    ]

    cited = [q for q, a in answerable if not a.refused]
    out += [
        "## Do the citations support the answer? (hand-labelled)",
        table(
            ["Yes", "Partly", "No", "Unlabelled"],
            [
                [str(sum(support.get(q.id) == s for q in cited)) for s in ("yes", "partly", "no")]
                + [str(sum(support.get(q.id) not in ("yes", "partly", "no") for q in cited))]
            ],
        ),
    ]

    groups = labelled_risks(queries, records, labels)
    strict, lenient = _separation(groups)
    out += [
        "## Hallucination-risk score vs. labels (first check per answer)",
        table(
            ["Label", "Answers", "Mean risk"],
            [
                [
                    label,
                    str(len(groups.get(label, []))),
                    _fmt(statistics.fmean(groups[label]) if groups.get(label) else None),
                ]
                for label in LABELS
            ],
        ),
        f"AUROC wrong vs correct: **{_fmt(strict)}**; wrong or partial vs correct: "
        f"**{_fmt(lenient)}** (0.5 = chance, 1.0 = every worse answer scored riskier).",
        "### Per check type",
        table(
            ["Check", "AUROC strict", "AUROC lenient"],
            [
                [kind, *map(_fmt, _separation(signal_risks(queries, records, labels, kind=kind)))]
                for kind in SIGNALS
            ],
        ),
    ]

    stable = stability(records)
    flips = sum(_level(s.low) != _level(s.high) for _, s in stable)
    out += [
        "## Stability (same answer checked repeatedly)",
        table(
            ["Question", "Mean", "Std", "Low", "High"],
            [[qid, _fmt(s.mean), _fmt(s.std), _fmt(s.low), _fmt(s.high)] for qid, s in stable],
        )
        if stable
        else "No answer was checked more than once.",
        f"{flips} of {len(stable)} answers changed Low/Medium/High level between runs.",
    ]
    runs = max((len(r.checks) for r in records.values()), default=0)
    if runs > 1:
        per_run = per_run_separation(queries, records, labels, runs=runs)
        out += [
            "### Does the separation survive re-checking? (lenient AUROC per run)",
            table(
                ["Answers", *(f"Run {k}" for k in range(1, runs + 1))],
                [[str(sum(len(r.checks) >= runs for r in records.values())), *map(_fmt, per_run)]],
            ),
        ]

    ask_s = [r.ask_seconds for r in records.values() if r.ask_seconds is not None]
    check_s = [c.seconds for r in records.values() for c in r.checks]
    errors = sum(len(r.errors) for r in records.values())
    out += [
        "## Latency (seconds)",
        table(
            ["Request", "Count", "Mean", "Median", "Max"],
            [
                [
                    name,
                    str(len(xs)),
                    _fmt(statistics.fmean(xs)),
                    _fmt(statistics.median(xs)),
                    _fmt(max(xs)),
                ]
                for name, xs in (("answer", ask_s), ("check", check_s))
                if xs
            ],
        ),
        f"{errors} failed requests were recorded (retried on later runs).",
    ]

    SUMMARY_PATH.write_text("\n\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
