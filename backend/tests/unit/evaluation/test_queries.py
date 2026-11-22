import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.queries import load_queries


def _line(**overrides: object) -> str:
    query = {
        "id": "q-01",
        "paper": "paper.pdf",
        "type": "fact",
        "answerable": True,
        "question": "What is it?",
        "expected_pages": [3],
        "reference": "It is X.",
    } | overrides
    return json.dumps(query)


def test_load_queries_reads_one_query_per_line(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text(_line(id="a") + "\n" + _line(id="b", expected_pages=[1, 2]) + "\n")

    queries = load_queries(path)

    assert [q.id for q in queries] == ["a", "b"]
    assert queries[1].expected_pages == [1, 2]


def test_paper_wording_is_optional_and_kept_when_given(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text(_line(id="a") + "\n" + _line(id="b", paper_wording="Original?") + "\n")

    first, second = load_queries(path)

    assert first.paper_wording is None
    assert second.paper_wording == "Original?"


def test_load_queries_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text("\n" + _line() + "\n\n")

    assert len(load_queries(path)) == 1


def test_load_queries_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text(_line(id="same") + "\n" + _line(id="same") + "\n")

    with pytest.raises(ValueError, match="same"):
        load_queries(path)


def test_load_queries_rejects_an_unknown_question_type(tmp_path: Path) -> None:
    path = tmp_path / "q.jsonl"
    path.write_text(_line(type="trivia") + "\n")

    with pytest.raises(ValidationError):
        load_queries(path)


def test_answerable_query_must_name_expected_pages(tmp_path: Path) -> None:
    # Without pages, retrieval could never count as a hit; that's a typo, not a result.
    path = tmp_path / "q.jsonl"
    path.write_text(_line(expected_pages=[]) + "\n")

    with pytest.raises(ValidationError):
        load_queries(path)
