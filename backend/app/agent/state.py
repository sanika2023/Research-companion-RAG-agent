import operator
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, TypedDict

from langgraph.types import StreamWriter

from app.retrieval.hybrid import SearchHit

QuestionKind = Literal["simple", "multi_step"]


@dataclass(frozen=True)
class Citation:
    number: int  # the [n] used in the answer text
    chunk_id: uuid.UUID
    page: int
    text: str
    bbox: list[list[float]]


class AgentState(TypedDict, total=False):
    """Shared state; each node returns only the keys it changes."""

    question: str  # always set by the caller; total=False because nodes return partial updates
    kind: QuestionKind
    sub_questions: list[str]
    passages: list[SearchHit]  # passage [n] is passages[n - 1]
    draft: str  # raw model answer before citation checking
    answer: str
    citations: list[Citation]
    refused: bool
    # Notable events for auditing, e.g. "invalid_citations_removed". operator.add makes
    # LangGraph append each node's flags instead of overwriting earlier ones.
    flags: Annotated[list[str], operator.add]


class Node(Protocol):
    # LangGraph matches nodes by a parameter literally named `state`.
    def __call__(self, state: AgentState) -> Awaitable[AgentState]: ...


class StreamingNode(Protocol):
    # LangGraph injects a `writer` for sending custom stream events (e.g. answer tokens).
    def __call__(
        self, state: AgentState, *, writer: StreamWriter = ...
    ) -> Awaitable[AgentState]: ...


# Hybrid search already bound to the selected paper (and a DB session).
Search = Callable[[str], Awaitable[list[SearchHit]]]
