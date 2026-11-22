import uuid

import pytest

from app.evaluation.answers import AnswerRecord, Check
from app.evaluation.queries import Query
from app.evaluation.summary import labelled_risks, per_run_separation, signal_risks, stability
from app.schemas.ask import AskResponse
from app.schemas.diagnose import DiagnoseResponse, SignalOut

DOC = uuid.uuid4()


def _query(qid: str, *, answerable: bool = True) -> Query:
    return Query(
        id=qid,
        paper="p.pdf",
        type="fact" if answerable else "unanswerable",
        answerable=answerable,
        question="Q?",
        expected_pages=[1] if answerable else [],
        reference="R",
    )


def _signal(kind: str, risk: float | None) -> SignalOut:
    return SignalOut.model_validate(
        {
            "kind": kind,
            "status": "ok" if risk is not None else "skipped",
            "weight": 1.0,
            "risk": risk,
            "similarity": None,
            "claim_agreement": None,
            "contradictions": None,
            "question": None,
            "answer": None,
            "refused": False,
        }
    )


def _record(qid: str, *risks: float | None, paraphrase: float | None = None) -> AnswerRecord:
    answer = AskResponse(
        doc_id=DOC,
        question="Q?",
        answer="A [1].",
        citations=[],
        refused=False,
        sub_questions=[],
        flags=[],
        passage_ids=[uuid.uuid4()],
    )
    checks = [
        Check(
            report=DiagnoseResponse(
                doc_id=DOC,
                uncertainty=r,
                signals=[_signal("paraphrase", paraphrase)],
                claims=[],
                flags=[],
            ),
            seconds=1.0,
        )
        for r in risks
    ]
    return AnswerRecord(id=qid, answer=answer, ask_seconds=1.0, checks=checks)


def test_labelled_risks_pair_each_label_with_the_first_check_score() -> None:
    queries = [_query("a"), _query("b"), _query("c")]
    records = {"a": _record("a", 0.1, 0.5), "b": _record("b", 0.4), "c": _record("c", 0.2)}
    labels = {"a": "correct", "b": "wrong", "c": "partial"}

    by_label = labelled_risks(queries, records, labels)

    assert by_label == {"correct": [0.1], "wrong": [0.4], "partial": [0.2]}


def test_labelled_risks_skip_unanswerable_unlabelled_and_unscored_answers() -> None:
    queries = [_query("u", answerable=False), _query("n"), _query("s")]
    records = {"u": _record("u", 0.3), "n": _record("n", 0.3), "s": _record("s", None)}
    labels = {"u": "correct", "n": "", "s": "wrong"}

    assert labelled_risks(queries, records, labels) == {}


def test_signal_risks_use_one_check_type_and_skip_where_it_did_not_run() -> None:
    queries = [_query("a"), _query("b")]
    records = {
        "a": _record("a", 0.2, paraphrase=0.6),
        "b": _record("b", 0.2, paraphrase=None),
    }
    labels = {"a": "wrong", "b": "correct"}

    assert signal_risks(queries, records, labels, kind="paraphrase") == {"wrong": [0.6]}


def test_per_run_separation_scores_each_repeat_on_the_answers_checked_every_time() -> None:
    queries = [_query("w"), _query("r"), _query("once")]
    records = {
        "w": _record("w", 0.5, 0.1),  # riskier than "r" on run 1, less risky on run 2
        "r": _record("r", 0.2, 0.3),
        "once": _record("once", 0.9),  # not checked on every run, so left out
    }
    labels = {"w": "wrong", "r": "correct", "once": "wrong"}

    assert per_run_separation(queries, records, labels, runs=2) == [1.0, 0.0]


def test_stability_summarises_answers_checked_more_than_once() -> None:
    records = {"a": _record("a", 0.1, 0.3), "b": _record("b", 0.2)}

    [(qid, summary)] = stability(records)

    assert qid == "a"
    assert summary.mean == pytest.approx(0.2)
    assert (summary.low, summary.high) == (0.1, 0.3)
