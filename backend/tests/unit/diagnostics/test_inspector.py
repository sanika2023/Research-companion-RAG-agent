import json

import pytest

from app.agent.prompts import NOT_FOUND
from app.core.config import DiagnosticsSettings
from app.diagnostics.inspector import Original, Report, Signal, inspect
from app.llm.base import M, Tier
from app.llm.gemini import LLMUnavailableError
from app.retrieval.hybrid import SearchHit
from tests.conftest import FakeEmbedder, FakeLLM
from tests.unit.agent.helpers import hit

SETTINGS = DiagnosticsSettings(similarity_floor=0.7, drop_cited_weight=0.0, concurrency=2)
JUDGE = "agree with an original answer"  # appears only in the judge prompt
REWRITE = "Rewrite the question"  # appears only in the paraphrase prompt
SYNTH = "numbered passages"  # appears only in the answer prompt
ANSWER = "MetaQA uses metamorphic relations [1]."
EVIDENCE, OTHER = hit("MetaQA uses MRs.", page=3), hit("Related work.", page=9)
DISTRACTOR = hit("DISTRACTOR: the appendix lists hyperparameters.", page=20)
EVERY = ("paraphrase", "reorder", "distractor", "drop_cited")


def judged(claims: list[str], verdicts: dict[str, list[str]]) -> str:
    answers = [{"id": key, "verdicts": v} for key, v in verdicts.items()]
    return json.dumps({"claims": claims, "answers": answers})


def all_agree(*keys: str) -> str:
    return judged(["MetaQA uses metamorphic relations."], {k: ["agrees"] for k in keys})


def original(answer: str = ANSWER, passages: list[SearchHit] | None = None) -> Original:
    return Original(
        question="What does MetaQA use?",
        answer=answer,
        passages=[EVIDENCE, OTHER] if passages is None else passages,
    )


async def run(
    llm: FakeLLM, item: Original | None = None, distractor: SearchHit | None = DISTRACTOR
) -> Report:
    return await inspect(
        item or original(),
        llm=llm,
        embedder=FakeEmbedder(),
        distractor=distractor,
        settings=SETTINGS,
    )


def signal(report: Report, kind: str) -> Signal:
    return next(s for s in report.signals if s.kind == kind)


async def test_an_answer_that_never_changes_scores_zero_uncertainty() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "How does MetaQA work?", SYNTH: ANSWER})

    report = await run(llm)

    assert report.uncertainty == pytest.approx(0.0)
    assert [s.kind for s in report.signals] == list(EVERY)
    assert all(s.status == "ok" for s in report.signals)
    assert signal(report, "reorder").similarity == pytest.approx(1.0)
    assert report.claims == ["MetaQA uses metamorphic relations."]


async def test_an_answer_that_changes_under_a_distractor_raises_uncertainty() -> None:
    verdicts = {"paraphrase": ["agrees"], "reorder": ["agrees"], "distractor": ["contradicts"]}
    llm = FakeLLM(
        {
            JUDGE: judged(["c"], {**verdicts, "drop_cited": ["agrees"]}),
            REWRITE: "How does MetaQA work?",
            "DISTRACTOR": "MetaQA tunes hyperparameters [1].",
            SYNTH: ANSWER,
        }
    )

    report = await run(llm)

    distractor = signal(report, "distractor")
    assert distractor.similarity == 0.0  # unrelated text falls below the floor
    assert distractor.claim_agreement == 0.0
    assert distractor.contradictions == 1
    assert distractor.risk == pytest.approx(1.0)
    assert report.uncertainty == pytest.approx(1 / 3)  # drop_cited is unweighted by default


async def test_drop_cited_risk_is_high_when_the_answer_survives_without_its_evidence() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "Reworded?", SYNTH: ANSWER})

    report = await run(llm)

    dropped = signal(report, "drop_cited")
    assert dropped.risk == pytest.approx(1.0)
    assert dropped.weight == 0.0


async def test_every_model_call_uses_the_light_model() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "Reworded?", SYNTH: ANSWER})

    await run(llm)

    assert set(llm.tiers) == {"light"}


async def test_the_paraphrase_run_answers_the_reworded_question() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "How does MetaQA work?", SYNTH: ANSWER})

    report = await run(llm)

    assert signal(report, "paraphrase").question == "How does MetaQA work?"
    assert signal(report, "reorder").question == "What does MetaQA use?"
    assert any("How does MetaQA work?" in p and SYNTH in p for p in llm.prompts)


async def test_a_perturbed_refusal_counts_as_full_disagreement_without_asking_the_judge() -> None:
    llm = FakeLLM(
        {
            JUDGE: all_agree("reorder", "distractor", "drop_cited"),
            REWRITE: "Reworded?",
            "Reworded?": NOT_FOUND,
            SYNTH: ANSWER,
        }
    )

    report = await run(llm)

    paraphrase = signal(report, "paraphrase")
    assert paraphrase.refused is True
    assert (paraphrase.similarity, paraphrase.claim_agreement) == (0.0, 0.0)
    assert paraphrase.risk == pytest.approx(1.0)
    [judge_prompt] = [p for p in llm.prompts if JUDGE in p]
    assert 'id="paraphrase"' not in judge_prompt


async def test_drop_cited_is_skipped_when_the_answer_cites_nothing() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "Reworded?", SYNTH: "No markers."})

    report = await run(llm, original(answer="No markers."))

    assert signal(report, "drop_cited").status == "skipped"
    assert signal(report, "drop_cited").risk is None


async def test_distractor_is_skipped_when_the_paper_has_no_spare_passage() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "Reworded?", SYNTH: ANSWER})

    report = await run(llm, distractor=None)

    assert signal(report, "distractor").status == "skipped"


async def test_dropping_the_only_passage_is_a_refusal_without_a_model_call() -> None:
    llm = FakeLLM({JUDGE: all_agree(*EVERY), REWRITE: "Reworded?", SYNTH: ANSWER})

    report = await run(llm, original(passages=[EVIDENCE]), distractor=None)

    assert signal(report, "reorder").status == "skipped"  # one passage has only one order
    assert signal(report, "drop_cited").refused is True
    assert sum(SYNTH in p for p in llm.prompts) == 1  # only the paraphrase rerun


class FailingLLM(FakeLLM):
    """Raises like an overloaded model whenever the prompt contains one of `fail_on`."""

    def __init__(self, responses: dict[str, str], fail_on: tuple[str, ...]) -> None:
        super().__init__(responses)
        self.fail_on = fail_on

    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str:
        self._fail_if_matched(prompt)
        return await super().complete(prompt, tier=tier)

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        self._fail_if_matched(prompt)
        return await super().complete_json(prompt, schema, tier=tier)

    def _fail_if_matched(self, prompt: str) -> None:
        if any(key in prompt for key in self.fail_on):
            raise LLMUnavailableError("overloaded")


async def test_a_failed_run_is_reported_and_left_out_of_the_score() -> None:
    llm = FailingLLM(
        {JUDGE: all_agree("reorder", "distractor", "drop_cited"), SYNTH: ANSWER},
        fail_on=(REWRITE,),
    )

    report = await run(llm)

    assert signal(report, "paraphrase").status == "failed"
    assert signal(report, "paraphrase").risk is None
    assert report.uncertainty == pytest.approx(0.0)


async def test_inspection_fails_when_every_run_fails() -> None:
    llm = FailingLLM({}, fail_on=(REWRITE, SYNTH))

    with pytest.raises(LLMUnavailableError):
        await run(llm)


async def test_without_the_judge_the_score_falls_back_to_embedding_similarity() -> None:
    llm = FailingLLM({REWRITE: "Reworded?", SYNTH: ANSWER}, fail_on=(JUDGE,))

    report = await run(llm)

    assert "judge_failed" in report.flags
    assert signal(report, "reorder").claim_agreement is None
    assert report.uncertainty == pytest.approx(0.0)  # identical answers, similarity 1


async def test_a_judgement_with_the_wrong_number_of_verdicts_is_ignored_for_that_answer() -> None:
    verdicts = {k: ["agrees"] for k in EVERY} | {"reorder": ["agrees", "agrees"]}
    llm = FakeLLM({JUDGE: judged(["one claim"], verdicts), REWRITE: "R?", SYNTH: ANSWER})

    report = await run(llm)

    assert signal(report, "reorder").claim_agreement is None
    assert signal(report, "paraphrase").claim_agreement == 1.0
