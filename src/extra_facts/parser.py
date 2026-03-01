from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Question

QUESTION_RE = re.compile(r"^(E\d[A-Z]\d{2})\s*\(([ABCD])\)\s*(.*)$")
CHOICE_RE = re.compile(r"^([ABCD])\.\s+(.*)$")
REMOVE_MARKER_RE = re.compile(r"\b(withdrawn|removed|cancelled|deleted)\b", re.IGNORECASE)


class ParseError(RuntimeError):
    pass


def parse_questions(raw_text: str) -> tuple[list[Question], int]:
    lines = _normalize_lines(raw_text)
    questions: list[Question] = []
    excluded = 0

    i = 0
    while i < len(lines):
        match = QUESTION_RE.match(lines[i])
        if match is None:
            i += 1
            continue

        question_id = match.group(1)
        correct_choice = match.group(2)
        question_text_parts = [match.group(3).strip()]
        choices: dict[str, str] = {}
        current_choice: str | None = None

        i += 1
        while i < len(lines) and QUESTION_RE.match(lines[i]) is None:
            line = lines[i]
            choice_match = CHOICE_RE.match(line)
            if choice_match:
                choice_key = choice_match.group(1)
                current_choice = choice_key
                choices[choice_key] = choice_match.group(2).strip()
            elif current_choice is not None:
                choices[current_choice] = f"{choices[current_choice]} {line}".strip()
            else:
                question_text_parts.append(line)
            i += 1

        question_text = _clean_text(" ".join(question_text_parts))
        choices = {key: _clean_text(value) for key, value in choices.items()}

        if _is_withdrawn(question_text, choices):
            excluded += 1
            continue

        # Errata/citation references can look like question IDs but do not
        # include full A-D answer choices; skip those artifacts.
        if len(choices) < 4:
            continue

        if correct_choice not in choices:
            sorted_choices = sorted(choices)
            raise ParseError(
                f"Question {question_id} missing correct choice "
                f"{correct_choice}; choices={sorted_choices}"
            )

        group = question_id[:3]
        subelement = question_id[:2]
        questions.append(
            Question(
                question_id=question_id,
                correct_choice=correct_choice,
                question_text=question_text,
                choices=choices,
                group=group,
                subelement=subelement,
            )
        )

    return questions, excluded


def _normalize_lines(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r", "\n")
    result: list[str] = []
    for line in normalized.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("SUBELEMENT") or stripped.startswith("Group"):
            continue
        result.append(stripped)
    return result


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_withdrawn(question_text: str, choices: dict[str, str]) -> bool:
    if REMOVE_MARKER_RE.search(question_text):
        return True
    return any(REMOVE_MARKER_RE.search(text) for text in choices.values())


def group_questions(questions: Iterable[Question]) -> dict[str, list[Question]]:
    grouped: dict[str, list[Question]] = {}
    for question in questions:
        grouped.setdefault(question.group, []).append(question)
    return grouped
