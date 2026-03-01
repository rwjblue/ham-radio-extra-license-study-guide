from __future__ import annotations

from pathlib import Path

from extra_facts.parser import extract_pool_metadata, parse_questions


def test_parse_questions_handles_multiline_and_withdrawn() -> None:
    fixture = Path("tests/fixtures/pool_snippet_extracted.txt").read_text(encoding="utf-8")

    questions, excluded = parse_questions(fixture)

    assert excluded == 1
    assert len(questions) == 3

    first = questions[0]
    assert first.question_id == "E1A01"
    assert first.correct_choice == "A"
    assert first.choices["A"] == "160, 75, 40, 20, 15, and 10 meters"

    second = questions[1]
    assert second.correct_choice == "C"
    assert "normal communication systems" in second.choices["C"]
    assert second.question_text.startswith("Which of the following")

    assert [q.group for q in questions] == ["E1A", "E1A", "E1B"]


def test_extract_pool_metadata_captures_subelement_and_group_titles() -> None:
    fixture = Path("tests/fixtures/pool_snippet_extracted.txt").read_text(encoding="utf-8")
    metadata = extract_pool_metadata(fixture)

    assert metadata.subelement_titles["E1"] == "COMMISSION'S RULES"
    assert metadata.group_titles["E1A"].startswith("Frequency privileges")
