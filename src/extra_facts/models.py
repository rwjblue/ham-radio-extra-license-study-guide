from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedQuestion:
    question_id: str
    correct_choice: str
    question_text: str
    choices: dict[str, str]
    group: str
    subelement: str


@dataclass(frozen=True)
class PoolQuestion:
    question_id: str
    question_text: str
    choices: list[str]
    correct_choice_index: int
    group: str
    subelement: str

    @property
    def correct_answer(self) -> str:
        return self.choices[self.correct_choice_index]


@dataclass(frozen=True)
class QuestionPool:
    schema_version: int
    excluded_count: int
    questions: list[PoolQuestion]


@dataclass(frozen=True)
class BuildSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path
    text_path: Path
    pdf_path: Path


@dataclass(frozen=True)
class ExtractSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path
