from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


def _empty_str_map() -> dict[str, str]:
    return {}


def _empty_str_list() -> list[str]:
    return []


def _empty_question_image_list() -> list[QuestionImage]:
    return []


@dataclass(frozen=True)
class QuestionImage:
    path: str | None = None
    data_base64: str | None = None
    data_url: str | None = None
    media_type: str | None = None


@dataclass(frozen=True)
class ParsedQuestion:
    question_id: str
    correct_choice: str
    question_text: str
    choices: dict[str, str]
    group: str
    subelement: str
    image_paths: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class PoolQuestion:
    question_id: str
    question_text: str
    choices: list[str]
    correct_choice_index: int
    group: str
    subelement: str
    image_paths: list[str] = field(default_factory=_empty_str_list)
    images: list[QuestionImage] = field(default_factory=_empty_question_image_list)
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
    dark_pdf_path: Path | None = None
    epub_path: Path | None = None


@dataclass(frozen=True)
class AudioScriptSummary:
    question_count: int
    group_count: int
    excluded_count: int
    intermediate_path: Path
    script_path: Path
    chapters_dir: Path
    chapters_manifest_path: Path
    chapter_count: int


@dataclass(frozen=True)
class AudioRenderSummary:
    chapter_count: int
    manifest_in_path: Path
    manifest_out_path: Path
    chapters_audio_dir: Path
    merged_audio_path: Path | None
    total_duration_seconds: float
    chapter_markers_embedded: bool
    chapters_rendered: int
    chapters_reused: int


@dataclass(frozen=True)
class AudioVerifySummary:
    manifest_path: Path
    chapter_count: int
    chapter_markers_verified: bool
    merged_audio_path: Path | None
    total_duration_seconds: float


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
    answer_explanation: str
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
    subelement_friendly_titles: dict[str, str] = field(default_factory=_empty_str_map)
    group_friendly_titles: dict[str, str] = field(default_factory=_empty_str_map)
