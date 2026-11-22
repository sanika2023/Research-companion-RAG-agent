import uuid
from pathlib import Path

from app.evaluation.answers import AnswerRecord, Check, checkable, load_records, plan, save_records
from app.evaluation.queries import Query
from app.schemas.ask import AskResponse
from app.schemas.diagnose import DiagnoseResponse

DOC = uuid.uuid4()


def _query(qid: str) -> Query:
    return Query(
        id=qid,
        paper="p.pdf",
        type="fact",
        answerable=True,
        question="Q?",
        expected_pages=[1],
        reference="R",
    )


def _answer(*, refused: bool = False, passages: int = 1) -> AskResponse:
    return AskResponse(
        doc_id=DOC,
        question="Q?",
        answer="A [1].",
        citations=[],
        refused=refused,
        sub_questions=[],
        flags=[],
        passage_ids=[uuid.uuid4() for _ in range(passages)],
    )


def _check() -> Check:
    report = DiagnoseResponse(doc_id=DOC, uncertainty=0.1, signals=[], claims=[], flags=[])
    return Check(report=report, seconds=5.0)


def _record(qid: str, answer: AskResponse, checks: int = 0) -> AnswerRecord:
    return AnswerRecord(id=qid, answer=answer, ask_seconds=2.0, checks=[_check()] * checks)


def test_a_question_without_a_record_needs_an_answer_and_all_checks() -> None:
    [step] = plan([_query("a")], records={}, checks=2)

    assert (step.query.id, step.ask, step.checks) == ("a", True, 2)


def test_an_answered_question_only_needs_its_missing_checks() -> None:
    records = {"a": _record("a", _answer(), checks=1)}

    [step] = plan([_query("a")], records=records, checks=3)

    assert (step.ask, step.checks) == (False, 2)


def test_finished_questions_are_left_out_of_the_plan() -> None:
    records = {"a": _record("a", _answer(), checks=1)}

    assert plan([_query("a")], records=records, checks=1) == []


def test_refused_answers_are_never_checked() -> None:
    records = {"a": _record("a", _answer(refused=True))}

    assert plan([_query("a")], records=records, checks=3) == []


def test_a_failed_answer_is_asked_again() -> None:
    records = {"a": AnswerRecord(id="a", answer=None, ask_seconds=None, checks=[], errors=["503"])}

    [step] = plan([_query("a")], records=records, checks=1)

    assert step.ask


def test_checkable_matches_the_check_button_rule() -> None:
    assert checkable(_answer())
    assert not checkable(_answer(refused=True))
    assert not checkable(_answer(passages=0))


def test_records_survive_a_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "answers.jsonl"
    records = {"a": _record("a", _answer(), checks=2), "b": _record("b", _answer(refused=True))}

    save_records(path, records)

    assert load_records(path) == records


def test_loading_a_missing_file_gives_no_records(tmp_path: Path) -> None:
    assert load_records(tmp_path / "none.jsonl") == {}
