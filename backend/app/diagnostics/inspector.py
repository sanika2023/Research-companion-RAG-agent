"""Perturbation inspector: re-ask with controlled changes and measure how far the answer moves."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from app.agent import prompts
from app.agent.nodes.check_citations import NOT_FOUND_MESSAGE, check_citations
from app.agent.nodes.synthesize import make_synthesize
from app.agent.state import AgentState
from app.core.config import DiagnosticsSettings
from app.diagnostics import score
from app.diagnostics.compare import Verdict, claim_agreement, cosine, rescale, strip_citations
from app.diagnostics.perturb import add_distractor, drop_most_cited, reorder
from app.diagnostics.score import Perturbation
from app.llm.base import Embedder, LLMClient
from app.llm.gemini import LLMUnavailableError
from app.retrieval.hybrid import SearchHit

MAX_CLAIMS = 8
Status = Literal["ok", "skipped", "failed"]


@dataclass(frozen=True)
class Original:
    question: str
    answer: str
    passages: list[SearchHit]  # exactly what the model saw, in order
    sub_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Signal:
    kind: Perturbation
    status: Status
    weight: float
    question: str | None = None  # asked in this run; differs from the original for paraphrase
    answer: str | None = None
    refused: bool = False
    similarity: float | None = None  # rescaled embedding similarity, 0-1
    claim_agreement: float | None = None
    contradictions: int | None = None
    risk: float | None = None


@dataclass(frozen=True)
class Report:
    uncertainty: float | None
    signals: list[Signal]
    claims: list[str]
    flags: list[str]


@dataclass(frozen=True)
class _Rerun:
    question: str
    answer: str
    refused: bool


class _OtherVerdicts(BaseModel):
    id: str
    verdicts: list[Verdict]


class _Judgement(BaseModel):
    claims: list[str]
    answers: list[_OtherVerdicts]


Plan = Callable[[], Awaitable[_Rerun]]


async def inspect(
    original: Original,
    *,
    llm: LLMClient,
    embedder: Embedder,
    distractor: SearchHit | None,
    settings: DiagnosticsSettings,
) -> Report:
    """Score how much an answer moves under each perturbation (0 = stable, 1 = unstable)."""
    runs = await _run_perturbations(original, llm, distractor, settings.concurrency)
    if not any(isinstance(r, _Rerun) for r in runs.values()):
        raise LLMUnavailableError("every perturbation run failed")

    # Refusals need no comparison: the answer is gone, so agreement is zero.
    answered = {k: r for k, r in runs.items() if isinstance(r, _Rerun) and not r.refused}
    similarities = await _similarities(embedder, original.answer, answered, settings)
    judgement, flags = await _judge(llm, original, answered)

    signals = [
        _signal(kind, outcome, settings.weights[kind], similarities.get(kind), judgement)
        for kind, outcome in runs.items()
    ]
    return Report(
        uncertainty=score.uncertainty({s.kind: s.risk for s in signals}, settings.weights),
        signals=signals,
        claims=judgement.claims if judgement else [],
        flags=flags,
    )


async def _run_perturbations(
    original: Original, llm: LLMClient, distractor: SearchHit | None, concurrency: int
) -> dict[Perturbation, _Rerun | Status]:
    limit = asyncio.Semaphore(concurrency)  # free-tier rate limits, not CPU, are the bottleneck
    synthesize = make_synthesize(llm, tier="light")

    async def rerun(question: str, passages: list[SearchHit]) -> _Rerun:
        if not passages:  # the agent refuses without evidence instead of asking the model
            return _Rerun(question, NOT_FOUND_MESSAGE, refused=True)
        state: AgentState = {
            "question": question,
            "sub_questions": original.sub_questions,
            "passages": passages,
            "flags": [],
        }
        async with limit:
            update = await synthesize(state)
        checked = check_citations({**state, **update})
        return _Rerun(question, checked["answer"], checked["refused"])

    async def paraphrased() -> _Rerun:
        prompt = prompts.PARAPHRASE.format(question=original.question)
        async with limit:
            question = (await llm.complete(prompt, tier="light")).strip()
        if not question:
            raise ValueError("empty paraphrase")
        return await rerun(question, original.passages)

    q, passages = original.question, original.passages
    dropped = drop_most_cited(passages, original.answer)
    plans: dict[Perturbation, Plan | None] = {
        "paraphrase": paraphrased,
        "reorder": (lambda: rerun(q, reorder(passages))) if len(passages) > 1 else None,
        "distractor": (
            (lambda: rerun(q, add_distractor(passages, distractor))) if distractor else None
        ),
        "drop_cited": (lambda: rerun(q, dropped)) if dropped is not None else None,
    }
    outcomes = await asyncio.gather(*(_attempt(plan) for plan in plans.values()))
    return dict(zip(plans, outcomes, strict=True))


async def _attempt(plan: Plan | None) -> _Rerun | Status:
    if plan is None:
        return "skipped"
    try:
        return await plan()
    except (LLMUnavailableError, ValueError):
        return "failed"  # one failed run shouldn't sink the others


async def _similarities(
    embedder: Embedder,
    answer: str,
    answered: dict[Perturbation, _Rerun],
    settings: DiagnosticsSettings,
) -> dict[Perturbation, float]:
    if not answered:
        return {}
    texts = [strip_citations(t) for t in [answer, *(r.answer for r in answered.values())]]
    first, *rest = await embedder.embed(texts)
    return {
        kind: rescale(cosine(first, vector), floor=settings.similarity_floor)
        for kind, vector in zip(answered, rest, strict=True)
    }


async def _judge(
    llm: LLMClient, original: Original, answered: dict[Perturbation, _Rerun]
) -> tuple[_Judgement | None, list[str]]:
    """One batched call: split the original into claims and check each other answer."""
    if not answered:
        return None, []
    prompt = prompts.JUDGE_AGREEMENT.format(
        max_claims=MAX_CLAIMS,
        question=original.question,
        original=original.answer,
        others=prompts.format_other_answers({k: r.answer for k, r in answered.items()}),
    )
    try:
        return await llm.complete_json(prompt, _Judgement, tier="light"), []
    except (LLMUnavailableError, ValueError):
        # Embedding similarity alone still gives a (cruder) score.
        return None, ["judge_failed"]


def _signal(
    kind: Perturbation,
    outcome: _Rerun | Status,
    weight: float,
    similarity: float | None,
    judgement: _Judgement | None,
) -> Signal:
    if isinstance(outcome, str):
        return Signal(kind, outcome, weight)
    if outcome.refused:
        claims: float | None = 0.0
        similarity, contradictions = 0.0, None
    else:
        verdicts = _verdicts_for(kind, judgement)
        claims = claim_agreement(verdicts) if verdicts is not None else None
        contradictions = verdicts.count("contradicts") if verdicts is not None else None
    agreement = score.agreement(similarity=similarity, claim_agreement=claims)
    return Signal(
        kind,
        "ok",
        weight,
        question=outcome.question,
        answer=outcome.answer,
        refused=outcome.refused,
        similarity=similarity,
        claim_agreement=claims,
        contradictions=contradictions,
        risk=score.risk(kind, agreement) if agreement is not None else None,
    )


def _verdicts_for(kind: Perturbation, judgement: _Judgement | None) -> list[Verdict] | None:
    if judgement is None:
        return None
    entry = next((a for a in judgement.answers if a.id == kind), None)
    # A verdict list that doesn't line up with the claims can't be trusted claim by claim.
    if entry is None or len(entry.verdicts) != len(judgement.claims):
        return None
    return entry.verdicts
