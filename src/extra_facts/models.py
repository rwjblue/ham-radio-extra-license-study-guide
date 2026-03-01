from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


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
    llm: LlmProse | None = None

    @property
    def correct_answer(self) -> str:
        return self.choices[self.correct_choice_index]


@dataclass(frozen=True)
class QuestionPool:
    schema_version: int
    excluded_count: int
    questions: list[PoolQuestion]
    metadata: PoolMetadata | None = None
    prose_schema_version: int | None = None
    prose_meta: ProseMeta | None = None


@dataclass(frozen=True)
class BuildSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path
    text_path: Path
    pdf_path: Path


@dataclass(frozen=True)
class AudioScriptSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path
    script_path: Path


@dataclass(frozen=True)
class ExtractSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path


@dataclass(frozen=True)
class ProseValidation:
    numbers_preserved: bool
    units_preserved: bool
    negation_preserved: bool


@dataclass(frozen=True)
class LlmProse:
    prose_fact: str
    status: Literal["accepted", "fallback", "error"]
    validation: ProseValidation
    source_hash: str
    confidence: float | None = None
    attempt_count: int = 1
    failure_reasons: list[str] | None = None
    last_candidate: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class ProseMeta:
    provider: str
    model: str
    prompt_version: str
    generated_at: str


@dataclass(frozen=True)
class PoolMetadata:
    subelement_titles: dict[str, str]
    group_titles: dict[str, str]
