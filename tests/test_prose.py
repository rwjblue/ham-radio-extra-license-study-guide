from __future__ import annotations

from extra_facts.models import PoolQuestion, QuestionPool
from extra_facts.prose import enrich_pool_with_prose, validate_prose


class _FakeClient:
    def __init__(self, prose: str) -> None:
        self._prose = prose

    def generate(
        self,
        question_id: str,
        question_text: str,
        correct_answer: str,
    ) -> tuple[str, float | None]:
        _ = (question_id, question_text, correct_answer)
        return self._prose, 0.9


def _pool(question: PoolQuestion) -> QuestionPool:
    return QuestionPool(schema_version=1, excluded_count=0, questions=[question])


def test_validate_prose_detects_missing_number() -> None:
    validation = validate_prose(
        question_text="What is the maximum power on 2200 meters?",
        correct_answer="1 W",
        prose_fact="The maximum power is low.",
    )
    assert validation.numbers_preserved is False


def test_enrich_pool_uses_fallback_when_validation_fails() -> None:
    question = PoolQuestion(
        question_id="E1A07",
        question_text="What is the maximum power on 2200 meters?",
        choices=["1 W", "5 W", "10 W", "100 W"],
        correct_choice_index=0,
        group="E1A",
        subelement="E1",
    )

    enriched, summary = enrich_pool_with_prose(
        _pool(question),
        client=_FakeClient("The maximum power is limited."),
        provider="test",
        model="fake",
        prompt_version="v1",
    )

    assert summary.generated == 1
    assert summary.fallback == 1
    assert enriched.questions[0].llm is not None
    assert enriched.questions[0].llm.status == "fallback"


def test_enrich_pool_accepts_valid_output() -> None:
    question = PoolQuestion(
        question_id="E1A07",
        question_text="What is the maximum power on 2200 meters?",
        choices=["1 W", "5 W", "10 W", "100 W"],
        correct_choice_index=0,
        group="E1A",
        subelement="E1",
    )

    enriched, summary = enrich_pool_with_prose(
        _pool(question),
        client=_FakeClient("The maximum power on 2200 meters is 1 W."),
        provider="test",
        model="fake",
        prompt_version="v1",
    )

    assert summary.accepted == 1
    assert enriched.questions[0].llm is not None
    assert enriched.questions[0].llm.status == "accepted"
