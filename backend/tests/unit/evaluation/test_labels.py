import uuid
from pathlib import Path

from app.evaluation.answers import AnswerRecord
from app.evaluation.labels import label_rows, read_labels, write_labels
from app.evaluation.queries import Query
from app.schemas.ask import AskResponse, CitationOut

DOC = uuid.uuid4()


def _query(qid: str = "a") -> Query:
    return Query(
        id=qid,
        paper="p.pdf",
        type="fact",
        answerable=True,
        question="What is it?",
        expected_pages=[3],
        reference="It is X.",
    )


def _record(qid: str = "a", *, answer: str = "It is X [1].") -> AnswerRecord:
    citation = CitationOut(number=1, chunk_id=uuid.uuid4(), page=3, text="X is it.", bbox=[])
    response = AskResponse(
        doc_id=DOC,
        question="What is it?",
        answer=answer,
        citations=[citation],
        refused=False,
        sub_questions=[],
        flags=[],
        passage_ids=[citation.chunk_id],
    )
    return AnswerRecord(id=qid, answer=response, ask_seconds=1.0)


def test_a_row_shows_the_answer_next_to_the_reference_with_empty_labels() -> None:
    [row] = label_rows([_query()], {"a": _record()}, existing={})

    assert row["reference"] == "It is X."
    assert row["answer"] == "It is X [1]."
    assert row["cited_passages"] == "[1] p3: X is it."
    assert row["correctness"] == row["citations_support"] == row["notes"] == ""


def test_labels_already_filled_in_are_kept() -> None:
    existing = {"a": {"correctness": "correct", "citations_support": "yes", "notes": "ok"}}

    [row] = label_rows([_query()], {"a": _record()}, existing=existing)

    assert (row["correctness"], row["citations_support"], row["notes"]) == ("correct", "yes", "ok")


def test_a_changed_answer_keeps_old_labels_but_is_marked_for_review() -> None:
    # Labels describe one answer text; if it changed (e.g. re-asked), they may no longer fit.
    existing = {"a": {"answer": "Old answer.", "correctness": "wrong", "citations_support": "no"}}

    [row] = label_rows([_query()], {"a": _record()}, existing=existing)

    assert row["correctness"] == "wrong"
    assert "answer changed" in row["notes"]


def test_questions_without_an_answer_are_left_out() -> None:
    no_answer = AnswerRecord(id="a", answer=None, ask_seconds=None, errors=["503"])

    assert label_rows([_query()], {"a": no_answer}, existing={}) == []


def test_labels_survive_a_write_and_read(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    rows = label_rows([_query()], {"a": _record()}, existing={})
    rows[0]["correctness"] = "partial"

    write_labels(path, rows)

    assert read_labels(path)["a"]["correctness"] == "partial"
