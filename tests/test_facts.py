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
            answer_explanation="Short reason.",
            status="accepted",
            validation=ProseValidation(True, True, True),
            source_hash="sha256:test",
            confidence=0.9,
        ),
    )
    assert fact_sentence(q, mode="prose") == (
        "E2A02: This is cleaner prose.\nNotes: Short reason."
    )


def test_qa_mode_uses_question_and_answer_text() -> None:
    q = _question("E3A01", "What is the purpose of this test?", "To verify Q and A mode")
    assert fact_sentence(q, mode="qa") == (
        "E3A01: Q: What is the purpose of this test? A: To verify Q and A mode."
    )


def test_qa_mode_expands_all_choices_correct_answer() -> None:
    q = PoolQuestion(
        question_id="E3A03",
        question_text="Which statements are true?",
        choices=[
            "Statement one is true",
            "Statement two is true",
            "Statement three is true",
            "All of these are correct",
        ],
        correct_choice_index=3,
        group="E3A",
        subelement="E3",
    )
    assert fact_sentence(q, mode="qa") == (
        "E3A03: Q: Which statements are true? A: All of these are correct:\n\n"
        "  - Statement one is true\n"
        "  - Statement two is true\n"
        "  - Statement three is true"
    )


def test_qa_mode_appends_llm_explanation_when_present() -> None:
    q = _question("E3A02", "What is the purpose of this test?", "To verify Q and A mode")
    q = PoolQuestion(
        question_id=q.question_id,
        question_text=q.question_text,
        choices=q.choices,
        correct_choice_index=q.correct_choice_index,
        group=q.group,
        subelement=q.subelement,
        llm=LlmProse(
            prose_fact="Cleaner prose sentence.",
            answer_explanation="Because this mode now carries augmented context.",
            status="accepted",
            validation=ProseValidation(True, True, True),
            source_hash="sha256:test-qa",
            confidence=0.9,
        ),
    )
    assert fact_sentence(q, mode="qa") == (
        "E3A02: Q: What is the purpose of this test? A: To verify Q and A mode.\n"
        "Notes: Because this mode now carries augmented context."
    )


def test_tts_rewrites_half_and_quarter_wavelength() -> None:
    q_half = _question("E9Z01", "What is a common antenna length?", "1/2 wavelength")
    half_line = fact_sentence(q_half, mode="tts", omit_id=True)
    assert "half wavelength" in half_line
    assert "1 slash 2 wavelength" not in half_line

    q_quarter = _question("E9Z02", "What is another common antenna length?", "1/4 wavelengths")
    quarter_line = fact_sentence(q_quarter, mode="tts", omit_id=True)
    assert "quarter wavelengths" in quarter_line
    assert "1 slash 4 wavelengths" not in quarter_line

    q_half_hyphen = _question(
        "E9Z03", "What is a common antenna length with punctuation?", "1/2-wavelength"
    )
    half_hyphen_line = fact_sentence(q_half_hyphen, mode="tts", omit_id=True)
    assert "half wavelength" in half_hyphen_line
    assert "1 slash 2-wavelength" not in half_hyphen_line

    q_quarter_hyphen = _question(
        "E9Z04",
        "What is another common antenna length with punctuation?",
        "1/4-wavelength",
    )
    quarter_hyphen_line = fact_sentence(q_quarter_hyphen, mode="tts", omit_id=True)
    assert "quarter wavelength" in quarter_hyphen_line
    assert "1 slash 4-wavelength" not in quarter_hyphen_line
