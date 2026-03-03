from __future__ import annotations

import json
from pathlib import Path

from extra_facts.intermediate import read_question_pool, to_question_pool, write_question_pool
from extra_facts.models import (
    LlmProse,
    ParsedQuestion,
    PoolMetadata,
    PoolQuestion,
    ProseValidation,
    QuestionImage,
)

PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W6mQAAAAASUVORK5CYII="
)


def test_question_pool_round_trip(tmp_path: Path) -> None:
    parsed_questions = [
        ParsedQuestion(
            question_id="E1A01",
            correct_choice="B",
            question_text="What is true?",
            choices={"A": "wrong", "B": "right", "C": "no", "D": "never"},
            group="E1A",
            subelement="E1",
            image_paths=["assets/image1.png"],
        )
    ]

    pool = to_question_pool(parsed_questions, excluded_count=2)
    assert pool.schema_version == 1
    assert pool.excluded_count == 2
    assert pool.questions[0].correct_choice_index == 1
    assert pool.questions[0].correct_answer == "right"
    assert pool.questions[0].image_paths == ["assets/image1.png"]
    assert pool.questions[0].images == [QuestionImage(path="assets/image1.png")]

    target = tmp_path / "pool.json"
    write_question_pool(pool, target)

    loaded = read_question_pool(target)
    assert loaded == pool


def test_question_pool_reads_embedded_images(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "excluded_count": 0,
        "questions": [
            {
                "question_id": "E1A01",
                "question_text": "What is true?",
                "choices": ["wrong", "right", "no", "never"],
                "correct_choice_index": 1,
                "group": "E1A",
                "subelement": "E1",
                "images": [
                    {
                        "media_type": "image/png",
                        "data_base64": PNG_1X1_BASE64,
                    }
                ],
            }
        ],
    }

    pool_path = tmp_path / "embedded.json"
    pool_path.write_text(json.dumps(payload), encoding="utf-8")
    pool = read_question_pool(pool_path)

    question = pool.questions[0]
    assert question.image_paths == []
    assert len(question.images) == 1
    assert question.images[0].data_base64 is not None


def test_question_pool_round_trip_with_metadata(tmp_path: Path) -> None:
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
    metadata = PoolMetadata(
        subelement_titles={"E1": "COMMISSION RULES"},
        group_titles={"E1A": "Frequency privileges"},
        subelement_friendly_titles={"E1": "Operating Rules"},
        group_friendly_titles={"E1A": "Band Privileges"},
    )
    pool = to_question_pool(parsed_questions, metadata=metadata)

    target = tmp_path / "pool_with_meta.json"
    write_question_pool(pool, target)
    loaded = read_question_pool(target)
    assert loaded == pool


def test_question_pool_round_trip_with_llm_debug_fields(tmp_path: Path) -> None:
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
    pool = to_question_pool(parsed_questions)
    question = pool.questions[0]
    pool.questions[0] = PoolQuestion(
        question_id=question.question_id,
        question_text=question.question_text,
        choices=question.choices,
        correct_choice_index=question.correct_choice_index,
        group=question.group,
        subelement=question.subelement,
        llm=LlmProse(
            prose_fact="Fact sentence.",
            answer_explanation="Short reason.",
            status="fallback",
            validation=ProseValidation(
                numbers_preserved=False,
                units_preserved=True,
                negation_preserved=True,
            ),
            source_hash="sha256:test",
            confidence=None,
            attempt_count=3,
            failure_reasons=["numbers"],
            last_candidate="Bad candidate.",
            last_error="timeout",
        ),
    )

    target = tmp_path / "pool_with_llm.json"
    write_question_pool(pool, target)
    loaded = read_question_pool(target)
    assert loaded == pool
