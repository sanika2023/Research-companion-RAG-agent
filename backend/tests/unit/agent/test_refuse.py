from app.agent.nodes.check_citations import NOT_FOUND_MESSAGE
from app.agent.nodes.refuse import refuse


def test_refuse_answers_with_the_not_found_message_and_no_citations() -> None:
    update = refuse({"question": "q", "passages": []})

    assert update == {
        "answer": NOT_FOUND_MESSAGE,
        "citations": [],
        "refused": True,
        "flags": ["no_passages"],
    }
