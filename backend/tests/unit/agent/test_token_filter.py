from app.agent.prompts import NOT_FOUND
from app.agent.token_filter import NotFoundFilter


def run(*chunks: str) -> list[str]:
    """Feed chunks in order, then flush; returns what would be streamed at each step."""
    f = NotFoundFilter()
    return [f.feed(chunk) for chunk in chunks] + [f.flush()]


def test_ordinary_text_passes_through_immediately() -> None:
    assert run("The ", "answer [1].") == ["The ", "answer [1].", ""]


def test_possible_start_of_the_signal_is_held_until_ruled_out() -> None:
    assert run("NOT", "ably, X [1].") == ["", "NOTably, X [1].", ""]


def test_complete_signal_is_never_streamed() -> None:
    assert run("NOT_", "FOUND") == ["", "", ""]


def test_signal_with_surrounding_whitespace_is_never_streamed() -> None:
    assert run(" ", NOT_FOUND, "\n") == ["", "", "", ""]


def test_held_text_is_released_if_the_reply_ends_there() -> None:
    assert run("NOT") == ["", "NOT"]


def test_text_after_the_first_chunk_is_not_held_again() -> None:
    assert run("Yes. ", "NOT") == ["Yes. ", "NOT", ""]
