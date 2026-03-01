from __future__ import annotations

from pathlib import Path

from extra_facts.intermediate import read_question_pool, to_question_pool, write_question_pool
from extra_facts.models import ParsedQuestion


def test_question_pool_round_trip(tmp_path: Path) -> None:
    parsed_questions = [
        ParsedQuestion(
            question_id="E1A01",
            correct_choice="B",
            question_text="What is true?",
            choices={"A": "wrong", "B": "right", "C": "no", "D": "never"},
            group="E1A",
            subelement="E1",
        )
    ]

    pool = to_question_pool(parsed_questions, excluded_count=2)
    assert pool.schema_version == 1
    assert pool.excluded_count == 2
    assert pool.questions[0].correct_choice_index == 1
    assert pool.questions[0].correct_answer == "right"

    target = tmp_path / "pool.json"
    write_question_pool(pool, target)

    loaded = read_question_pool(target)
    assert loaded == pool
