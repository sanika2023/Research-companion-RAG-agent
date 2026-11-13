"""What the agent reports while it works; the API turns these into Server-Sent Events."""

from dataclasses import dataclass

from app.agent.state import AgentState


@dataclass(frozen=True)
class StepStarted:
    step: str  # "classify" | "decompose" | "retrieve" | "synthesize"


@dataclass(frozen=True)
class SubQuestions:
    questions: list[str]


@dataclass(frozen=True)
class Token:
    text: str  # raw answer text; Finished carries the citation-checked version


@dataclass(frozen=True)
class Finished:
    state: AgentState


AgentEvent = StepStarted | SubQuestions | Token | Finished
