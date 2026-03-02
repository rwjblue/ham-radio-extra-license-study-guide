from __future__ import annotations

from extra_facts.facts import fact_sentence
from extra_facts.models import LlmProse, PoolQuestion, ProseValidation


def _question(question_id: str, text: str, answer: str, correct_index: int = 0) -> PoolQuestion:
    return PoolQuestion(
        question_id=question_id,
        question_text=text,
        choices=[answer, "no", "no", "no"],
        correct_choice_index=correct_index,
        group=question_id[:3],
        subelement=question_id[:2],
    )


def test_what_is_transform() -> None:
    q = _question("E1A01", "What is the maximum symbol rate?", "1200 baud")
    assert fact_sentence(q, mode="literal") == "E1A01: The maximum symbol rate is 1200 baud."


def test_which_following_transform() -> None:
    q = _question("E1A02", "Which of the following is true?", "Option A")
    assert fact_sentence(q, mode="literal") == "E1A02: Which of the following is true: Option A."


def test_how_many_transform() -> None:
    q = _question("E1B01", "How many operators may transmit?", "Three")
    assert fact_sentence(q, mode="literal") == "E1B01: How many operators may transmit: Three."


def test_when_must_transform() -> None:
    q = _question("E1C01", "When must control operators identify?", "every 10 minutes")
    assert fact_sentence(q, mode="literal") == (
        "E1C01: When must control operators identify: every 10 minutes."
    )


def test_why_transform() -> None:
    q = _question("E1D01", "Why is this illegal?", "it exceeds the limit")
    assert fact_sentence(q, mode="literal") == "E1D01: It is illegal because it exceeds the limit."


def test_what_is_meant_by_transform() -> None:
    q = _question("E2A04", "What is meant by the mode of a satellite?", "uplink and downlink bands")
    assert fact_sentence(q, mode="literal") == (
        "E2A04: The mode of a satellite means uplink and downlink bands."
    )


def test_tts_expands_units_and_abbreviations() -> None:
    q = _question("E2A01", "What is the maximum EIRP?", "1500 W on HF")
    line = fact_sentence(q, mode="tts", omit_id=True)
    assert "equivalent isotropically radiated power" in line
    assert "1500 watts" in line
    assert "high frequency" in line


def test_tts_expands_ghz_unit() -> None:
    q = _question("E2A03", "What is the frequency?", "5.8 GHz")
    line = fact_sentence(q, mode="tts", omit_id=True)
    assert "5.8 gigahertz" in line
    assert "GHz" not in line


def test_prose_mode_uses_llm_fact() -> None:
    q = _question("E2A02", "Which of the following is true?", "Option A")
    q = PoolQuestion(
        question_id=q.question_id,
        question_text=q.question_text,
        choices=q.choices,
        correct_choice_index=q.correct_choice_index,
        group=q.group,
        subelement=q.subelement,
        llm=LlmProse(
            prose_fact="This is cleaner prose.",
            status="accepted",
            validation=ProseValidation(True, True, True),
            source_hash="sha256:test",
            confidence=0.9,
        ),
    )
    assert fact_sentence(q, mode="prose") == "E2A02: This is cleaner prose."
