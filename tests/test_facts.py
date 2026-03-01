from __future__ import annotations

from extra_facts.facts import fact_sentence
from extra_facts.models import Question


def _question(question_id: str, text: str, answer: str, correct: str = "A") -> Question:
    return Question(
        question_id=question_id,
        correct_choice=correct,
        question_text=text,
        choices={"A": answer, "B": "no", "C": "no", "D": "no"},
        group=question_id[:3],
        subelement=question_id[:2],
    )


def test_what_is_transform() -> None:
    q = _question("E1A01", "What is the maximum symbol rate?", "1200 baud")
    assert fact_sentence(q, mode="literal") == "E1A01: The maximum symbol rate is 1200 baud."


def test_which_following_transform() -> None:
    q = _question("E1A02", "Which of the following is true?", "Option A")
    assert "the correct choice is Option A" in fact_sentence(q, mode="literal")


def test_how_many_transform() -> None:
    q = _question("E1B01", "How many operators may transmit?", "Three")
    assert "the number is Three" in fact_sentence(q, mode="literal")


def test_when_must_transform() -> None:
    q = _question("E1C01", "When must control operators identify?", "every 10 minutes")
    assert fact_sentence(q, mode="literal") == (
        "E1C01: You must control operators identify when every 10 minutes."
    )


def test_tts_expands_units_and_abbreviations() -> None:
    q = _question("E2A01", "What is the maximum EIRP?", "1500 W on HF")
    line = fact_sentence(q, mode="tts", omit_id=True)
    assert "equivalent isotropically radiated power" in line
    assert "1500 watts" in line
    assert "high frequency" in line
