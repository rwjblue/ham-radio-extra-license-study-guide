from __future__ import annotations

import json
from pathlib import Path

from .models import ParsedQuestion, PoolQuestion, QuestionPool

CHOICE_ORDER = ("A", "B", "C", "D")
SCHEMA_VERSION = 1


def to_question_pool(
    parsed_questions: list[ParsedQuestion],
    excluded_count: int = 0,
) -> QuestionPool:
    questions: list[PoolQuestion] = []
    for parsed in parsed_questions:
        choices = [parsed.choices[label] for label in CHOICE_ORDER]
        correct_choice_index = CHOICE_ORDER.index(parsed.correct_choice)
        questions.append(
            PoolQuestion(
                question_id=parsed.question_id,
                question_text=parsed.question_text,
                choices=choices,
                correct_choice_index=correct_choice_index,
                group=parsed.group,
                subelement=parsed.subelement,
            )
        )
    return QuestionPool(
        schema_version=SCHEMA_VERSION,
        excluded_count=excluded_count,
        questions=questions,
    )


def write_question_pool(pool: QuestionPool, target: Path) -> None:
    payload: dict[str, object] = {
        "schema_version": pool.schema_version,
        "excluded_count": pool.excluded_count,
        "questions": [
            {
                "question_id": question.question_id,
                "question_text": question.question_text,
                "choices": question.choices,
                "correct_choice_index": question.correct_choice_index,
                "group": question.group,
                "subelement": question.subelement,
            }
            for question in pool.questions
        ],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_question_pool(path: Path) -> QuestionPool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions_payload = payload["questions"]

    questions = [
        PoolQuestion(
            question_id=question_payload["question_id"],
            question_text=question_payload["question_text"],
            choices=list(question_payload["choices"]),
            correct_choice_index=int(question_payload["correct_choice_index"]),
            group=question_payload["group"],
            subelement=question_payload["subelement"],
        )
        for question_payload in questions_payload
    ]

    return QuestionPool(
        schema_version=int(payload["schema_version"]),
        excluded_count=int(payload.get("excluded_count", 0)),
        questions=questions,
    )


def group_pool_questions(questions: list[PoolQuestion]) -> dict[str, list[PoolQuestion]]:
    grouped: dict[str, list[PoolQuestion]] = {}
    for question in questions:
        grouped.setdefault(question.group, []).append(question)
    return grouped
