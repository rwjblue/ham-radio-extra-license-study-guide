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
        feedback: str | None = None,
    ) -> tuple[str, float | None]:
        _ = (question_id, question_text, correct_answer, feedback)
        return self._prose, 0.9


class _SequencedClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.feedbacks: list[str | None] = []

    def generate(
        self,
        question_id: str,
        question_text: str,
        correct_answer: str,
        feedback: str | None = None,
    ) -> tuple[str, float | None]:
        _ = (question_id, question_text, correct_answer)
        self.calls += 1
        self.feedbacks.append(feedback)
        if self._responses:
            return self._responses.pop(0), 0.9
        return "Fallback response", 0.9


class _AlwaysErrorClient:
    def generate(
        self,
        question_id: str,
        question_text: str,
        correct_answer: str,
        feedback: str | None = None,
    ) -> tuple[str, float | None]:
        _ = (question_id, question_text, correct_answer, feedback)
        raise RuntimeError("boom")


def _pool(question: PoolQuestion) -> QuestionPool:
    return QuestionPool(schema_version=1, excluded_count=0, questions=[question])


def test_validate_prose_detects_missing_number() -> None:
    validation = validate_prose(
        question_text="What is the maximum power on 2200 meters?",
        correct_answer="1 W",
        prose_fact="The maximum power is low.",
    )
    assert validation.numbers_preserved is False


def test_validate_prose_does_not_treat_plain_letter_as_unit() -> None:
    validation = validate_prose(
        question_text=(
            "If an amateur station is installed aboard a ship or aircraft, "
            "what condition must be met before the station is operated?"
        ),
        correct_answer=(
            "Its operation must be approved by the master of the ship "
            "or the pilot in command of the aircraft"
        ),
        prose_fact=(
            "If an amateur station is installed aboard a ship or aircraft, "
            "its operation must be approved by the master of the ship "
            "or the pilot in command of the aircraft."
        ),
    )
    assert validation.units_preserved is True


def test_validate_prose_accepts_meter_abbreviation_equivalence() -> None:
    validation = validate_prose(
        question_text=(
            "Which of the following HF amateur bands include allocations for space stations?"
        ),
        correct_answer="40 meters, 20 meters, 15 meters, and 10 meters",
        prose_fact=(
            "The HF amateur bands that include allocations for space stations "
            "are 40 m, 20 m, 15 m, and 10 m."
        ),
    )
    assert validation.units_preserved is True


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
    assert enriched.questions[0].llm.attempt_count == 3
    assert enriched.questions[0].llm.failure_reasons == ["numbers", "units"]
    assert enriched.questions[0].llm.last_candidate == "The maximum power is limited."
    assert enriched.questions[0].llm.last_error is None


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
    assert enriched.questions[0].llm.attempt_count == 1
    assert enriched.questions[0].llm.failure_reasons is None
    assert enriched.questions[0].llm.last_candidate == "The maximum power on 2200 meters is 1 W."


def test_enrich_pool_retries_and_accepts_on_second_attempt() -> None:
    question = PoolQuestion(
        question_id="E1A07",
        question_text="What is the maximum power on 2200 meters?",
        choices=["1 W", "5 W", "10 W", "100 W"],
        correct_choice_index=0,
        group="E1A",
        subelement="E1",
    )
    client = _SequencedClient(
        responses=[
            "The maximum power is limited.",
            "The maximum power on 2200 meters is 1 W.",
        ]
    )

    enriched, summary = enrich_pool_with_prose(
        _pool(question),
        client=client,
        provider="test",
        model="fake",
        prompt_version="v1",
        max_attempts=3,
    )

    assert summary.accepted == 1
    assert summary.fallback == 0
    assert client.calls == 2
    assert client.feedbacks[0] is None
    assert client.feedbacks[1] is not None
    assert "failed validation" in str(client.feedbacks[1]).lower()
    assert enriched.questions[0].llm is not None
    assert enriched.questions[0].llm.status == "accepted"
    assert enriched.questions[0].llm.attempt_count == 2
    assert enriched.questions[0].llm.failure_reasons == ["numbers", "units"]


def test_enrich_pool_falls_back_after_max_attempts() -> None:
    question = PoolQuestion(
        question_id="E1A07",
        question_text="What is the maximum power on 2200 meters?",
        choices=["1 W", "5 W", "10 W", "100 W"],
        correct_choice_index=0,
        group="E1A",
        subelement="E1",
    )
    client = _SequencedClient(
        responses=[
            "The maximum power is limited.",
            "A station must be careful with power.",
            "Use as little power as possible.",
        ]
    )

    enriched, summary = enrich_pool_with_prose(
        _pool(question),
        client=client,
        provider="test",
        model="fake",
        prompt_version="v1",
        max_attempts=3,
    )

    assert summary.accepted == 0
    assert summary.fallback == 1
    assert client.calls == 3
    assert enriched.questions[0].llm is not None
    assert enriched.questions[0].llm.status == "fallback"
    assert enriched.questions[0].llm.attempt_count == 3
    assert enriched.questions[0].llm.failure_reasons == ["numbers", "units"]


def test_enrich_pool_records_error_debug_data() -> None:
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
        client=_AlwaysErrorClient(),
        provider="test",
        model="fake",
        prompt_version="v1",
        max_attempts=2,
    )

    assert summary.errors == 1
    assert enriched.questions[0].llm is not None
    assert enriched.questions[0].llm.status == "error"
    assert enriched.questions[0].llm.attempt_count == 2
    assert enriched.questions[0].llm.failure_reasons == ["llm_error"]
    assert enriched.questions[0].llm.last_error == "boom"
