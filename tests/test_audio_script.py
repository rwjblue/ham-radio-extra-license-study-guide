from __future__ import annotations

from pathlib import Path

from extra_facts.models import PoolMetadata, PoolQuestion
from extra_facts.render import write_audio_script


def _question(question_id: str, text: str, answer: str) -> PoolQuestion:
    return PoolQuestion(
        question_id=question_id,
        question_text=text,
        choices=[answer, "x", "y", "z"],
        correct_choice_index=0,
        group=question_id[:3],
        subelement=question_id[:2],
    )


def test_write_audio_script_adds_spoken_headers_and_omits_ids(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is the maximum symbol rate?", "1200 baud"),
        _question("E1A02", "Which of the following is true?", "Option A"),
        _question("E1B01", "How many operators may transmit?", "Three"),
    ]
    metadata = PoolMetadata(
        subelement_titles={"E1": "COMMISSION'S RULES"},
        group_titles={"E1A": "Frequency privileges", "E1B": "Station restrictions"},
    )

    path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="tts",
        omit_id=True,
        metadata=metadata,
    )

    content = path.read_text(encoding="utf-8")
    assert "Now starting SUBELEMENT E1 - COMMISSION'S RULES." in content
    assert "Group E1A - Frequency privileges." in content
    assert "Group E1B - Station restrictions." in content
    assert "E1A01:" not in content


def test_write_audio_script_can_include_ids(tmp_path: Path) -> None:
    questions = [_question("E1A01", "What is the maximum symbol rate?", "1200 baud")]

    path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=False,
    )

    content = path.read_text(encoding="utf-8")
    assert "E1A01: The maximum symbol rate is 1200 baud." in content
