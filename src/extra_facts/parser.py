from __future__ import annotations

import re
from collections.abc import Iterable

from .models import ParsedQuestion, PoolMetadata

QUESTION_RE = re.compile(r"^(E\d[A-Z]\d{2})\s*\(([ABCD])\)\s*(.*)$")
CHOICE_RE = re.compile(r"^([ABCD])\.\s+(.*)$")
GROUP_HEADING_RE = re.compile(r"^E\d[A-Z]\s+")
LEADING_CITATION_RE = re.compile(r"^(?:\[[^\]]+\]\s*)+")
REMOVE_MARKER_RE = re.compile(r"\b(withdrawn|removed|cancelled|deleted)\b", re.IGNORECASE)
SUBELEMENT_LINE_RE = re.compile(r"^SUBELEMENT\s+(E\d)\s*-\s*(.+)$", re.IGNORECASE)
GROUP_TITLE_RE = re.compile(r"^(E\d[A-Z])\s+(?!\d{2}\b)(.+)$")


class ParseError(RuntimeError):
    pass


def parse_questions(
    raw_text: str,
    question_images: dict[str, list[str]] | None = None,
) -> tuple[list[ParsedQuestion], int]:
    lines = _normalize_lines(raw_text)
    questions: list[ParsedQuestion] = []
    excluded = 0
    question_images = question_images or {}

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
            ParsedQuestion(
                question_id=question_id,
                correct_choice=correct_choice,
                question_text=question_text,
                choices=choices,
                group=group,
                subelement=subelement,
                image_paths=question_images.get(question_id, []),
            )
        )

    return questions, excluded


def extract_pool_metadata(raw_text: str) -> PoolMetadata:
    subelement_titles: dict[str, str] = {}
    group_titles: dict[str, str] = {}

    lines = [line.strip() for line in raw_text.replace("\r", "\n").split("\n")]
    for line in lines:
        if not line:
            continue
        subelement_match = SUBELEMENT_LINE_RE.match(line)
        if subelement_match is not None:
            subelement_code = subelement_match.group(1).upper()
            raw_title = subelement_match.group(2).strip()
            subelement_titles[subelement_code] = _clean_subelement_title(raw_title)
            continue

        group_match = GROUP_TITLE_RE.match(line)
        if group_match is not None:
            group_code = group_match.group(1).upper()
            raw_group_title = group_match.group(2).strip()
            if QUESTION_RE.match(line) is not None:
                continue
            group_titles[group_code] = _clean_group_title(raw_group_title)

    return PoolMetadata(
        subelement_titles=subelement_titles,
        group_titles=group_titles,
    )


def _normalize_lines(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r", "\n")
    result: list[str] = []
    for line in normalized.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if "~~" in stripped:
            stripped = stripped.replace("~~", "").strip()
            if not stripped:
                continue
        if stripped.startswith("SUBELEMENT") or stripped.startswith("Group"):
            continue
        if GROUP_HEADING_RE.match(stripped):
            continue
        result.append(stripped)
    return result


def _clean_text(value: str) -> str:
    value = LEADING_CITATION_RE.sub("", value)
    value = value.replace("~~", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_withdrawn(question_text: str, choices: dict[str, str]) -> bool:
    if REMOVE_MARKER_RE.search(question_text):
        return True
    return any(REMOVE_MARKER_RE.search(text) for text in choices.values())


def group_questions(questions: Iterable[ParsedQuestion]) -> dict[str, list[ParsedQuestion]]:
    grouped: dict[str, list[ParsedQuestion]] = {}
    for question in questions:
        grouped.setdefault(question.group, []).append(question)
    return grouped


def _clean_subelement_title(raw_title: str) -> str:
    title = re.sub(r"\[[^\]]+\]", "", raw_title)
    title = re.sub(r"\b\d+\s+Questions?\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+-\s+$", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip(" -")


def _clean_group_title(raw_title: str) -> str:
    title = re.sub(r"\s+", " ", raw_title)
    return title.strip()
