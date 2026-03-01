from __future__ import annotations

from pathlib import Path

from .downloader import download_source
from .extract import extract_text
from .models import BuildSummary
from .parser import parse_questions
from .render import write_outputs


def build_from_source(source_path: Path, out_dir: Path, mode: str, omit_id: bool) -> BuildSummary:
    text = extract_text(source_path)
    questions, excluded_count = parse_questions(text)
    text_path, pdf_path = write_outputs(questions, out_dir=out_dir, mode=mode, omit_id=omit_id)
    return BuildSummary(
        question_count=len(questions),
        group_count=len({q.group for q in questions}),
        excluded_count=excluded_count,
        text_path=text_path,
        pdf_path=pdf_path,
    )


def build_from_url(
    source_url: str,
    out_dir: Path,
    mode: str,
    omit_id: bool,
    cache: Path | None,
) -> BuildSummary:
    source_path = download_source(source_url, cache_dir=cache)
    return build_from_source(source_path, out_dir=out_dir, mode=mode, omit_id=omit_id)
