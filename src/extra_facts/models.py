from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Question:
    question_id: str
    correct_choice: str
    question_text: str
    choices: dict[str, str]
    group: str
    subelement: str


@dataclass(frozen=True)
class BuildOptions:
    out_dir: Path
    mode: str
    omit_id: bool


@dataclass(frozen=True)
class BuildSummary:
    question_count: int
    group_count: int
    excluded_count: int
    text_path: Path
    pdf_path: Path
