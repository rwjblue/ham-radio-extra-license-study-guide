from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .downloader import download_source
from .extract import extract_text
from .intermediate import read_question_pool, to_question_pool, write_question_pool
from .models import BuildSummary, ExtractSummary
from .parser import parse_questions
from .prose import OpenAIProseClient, ProseProgressUpdate, ProseRunSummary, enrich_pool_with_prose
from .render import write_outputs


def extract_pool_from_source(source_path: Path, pool_json_path: Path) -> ExtractSummary:
    text = extract_text(source_path)
    parsed_questions, excluded_count = parse_questions(text)
    pool = to_question_pool(parsed_questions, excluded_count=excluded_count)
    pool_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_question_pool(pool, pool_json_path)
    return ExtractSummary(
        question_count=len(pool.questions),
        group_count=len({q.group for q in pool.questions}),
        excluded_count=excluded_count,
        intermediate_path=pool_json_path,
    )


def extract_pool_from_url(
    source_url: str,
    pool_json_path: Path,
    cache: Path | None,
) -> ExtractSummary:
    source_path = download_source(source_url, cache_dir=cache)
    return extract_pool_from_source(source_path, pool_json_path=pool_json_path)


def build_from_pool_json(
    pool_json_path: Path,
    out_dir: Path,
    mode: str,
    omit_id: bool,
) -> BuildSummary:
    loaded_pool = read_question_pool(pool_json_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_path, pdf_path = write_outputs(
        loaded_pool.questions,
        out_dir=out_dir,
        mode=mode,
        omit_id=omit_id,
    )
    return BuildSummary(
        question_count=len(loaded_pool.questions),
        group_count=len({q.group for q in loaded_pool.questions}),
        excluded_count=loaded_pool.excluded_count,
        intermediate_path=pool_json_path,
        text_path=text_path,
        pdf_path=pdf_path,
    )


def generate_prose_for_pool(
    pool_json_path: Path,
    out_json_path: Path,
    model: str,
    prompt_version: str,
    max_questions: int | None,
    resume: bool,
    workers: int,
    max_attempts: int,
    progress_callback: Callable[[ProseProgressUpdate], None] | None = None,
) -> ProseRunSummary:
    pool = read_question_pool(pool_json_path)
    client = OpenAIProseClient(model=model, prompt_version=prompt_version)
    enriched_pool, summary = enrich_pool_with_prose(
        pool,
        client=client,
        provider="openai",
        model=model,
        prompt_version=prompt_version,
        max_questions=max_questions,
        resume=resume,
        workers=workers,
        max_attempts=max_attempts,
        progress_callback=progress_callback,
    )
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_question_pool(enriched_pool, out_json_path)
    return summary
