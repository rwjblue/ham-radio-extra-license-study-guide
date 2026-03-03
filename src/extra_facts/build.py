from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

from .audio import (
    DEFAULT_ELEVENLABS_OUTPUT_FORMAT,
    DEFAULT_TTS_INSTRUCTIONS,
    AudioRenderProgressUpdate,
    ElevenLabsTtsClient,
    OpenAITtsClient,
    TtsClient,
    render_audio_from_manifest,
)
from .audio_verify import verify_audio_from_manifest
from .downloader import download_source
from .extract import export_docx_media_for_questions, extract_docx_with_images, extract_text
from .intermediate import read_question_pool, to_question_pool, write_question_pool
from .models import (
    AudioRenderSummary,
    AudioScriptSummary,
    AudioVerifySummary,
    BuildSummary,
    ExtractSummary,
    PoolQuestion,
)
from .parser import extract_pool_metadata, parse_questions
from .prose import (
    OpenAIProseClient,
    ProseProgressUpdate,
    ProseRunSummary,
    enrich_pool_metadata_with_headings,
    enrich_pool_with_prose,
)
from .render import write_audio_script, write_outputs


def extract_pool_from_source(source_path: Path, pool_json_path: Path) -> ExtractSummary:
    question_images: dict[str, list[str]] = {}
    if source_path.suffix.lower() == ".docx":
        text, docx_image_paths = extract_docx_with_images(source_path)
        assets_dir = pool_json_path.parent / "assets"
        question_images = export_docx_media_for_questions(
            source_path,
            assets_dir,
            docx_image_paths,
        )
    else:
        text = extract_text(source_path)

    parsed_questions, excluded_count = parse_questions(text, question_images=question_images)
    metadata = extract_pool_metadata(text)
    pool = to_question_pool(parsed_questions, excluded_count=excluded_count, metadata=metadata)
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
    output_name = "qa" if mode == "qa" else "facts"
    text_path, pdf_path, dark_pdf_path, epub_path = write_outputs(
        loaded_pool.questions,
        out_dir=out_dir,
        mode=mode,
        omit_id=omit_id,
        metadata=loaded_pool.metadata,
        image_root_dir=pool_json_path.parent,
        txt_name=f"{output_name}.txt",
        pdf_name=f"{output_name}.pdf",
        dark_pdf_name=f"{output_name}-dark.pdf",
        epub_name=f"{output_name}.epub",
    )
    return BuildSummary(
        question_count=len(loaded_pool.questions),
        group_count=len({q.group for q in loaded_pool.questions}),
        excluded_count=loaded_pool.excluded_count,
        intermediate_path=pool_json_path,
        text_path=text_path,
        pdf_path=pdf_path,
        dark_pdf_path=dark_pdf_path,
        epub_path=epub_path,
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
    enriched_pool = enrich_pool_metadata_with_headings(
        enriched_pool,
        client=client,
    )
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    _copy_referenced_assets(
        questions=enriched_pool.questions,
        source_root=pool_json_path.parent,
        destination_root=out_json_path.parent,
    )
    write_question_pool(enriched_pool, out_json_path)
    return summary


def _copy_referenced_assets(
    questions: list[PoolQuestion],
    source_root: Path,
    destination_root: Path,
) -> None:
    if source_root.resolve() == destination_root.resolve():
        return

    for relative_path in _referenced_image_paths(questions):
        source_path = source_root / relative_path
        if not source_path.exists() or not source_path.is_file():
            continue
        target_path = destination_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def _referenced_image_paths(questions: list[PoolQuestion]) -> list[Path]:
    ordered_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for question in questions:
        image_paths = [*question.image_paths]
        image_paths.extend(image.path for image in question.images if image.path)
        for raw_path in image_paths:
            parsed = Path(raw_path)
            if parsed.is_absolute() or ".." in parsed.parts:
                continue
            if parsed in seen_paths:
                continue
            seen_paths.add(parsed)
            ordered_paths.append(parsed)
    return ordered_paths


def build_audio_script_from_pool_json(
    pool_json_path: Path,
    out_dir: Path,
    mode: str,
    omit_id: bool,
) -> AudioScriptSummary:
    loaded_pool = read_question_pool(pool_json_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path, chapters_dir, chapters_manifest_path = write_audio_script(
        loaded_pool.questions,
        out_dir=out_dir,
        mode=mode,
        omit_id=omit_id,
        metadata=loaded_pool.metadata,
        txt_name="script.txt",
    )
    return AudioScriptSummary(
        question_count=len(loaded_pool.questions),
        group_count=len({q.group for q in loaded_pool.questions}),
        excluded_count=loaded_pool.excluded_count,
        intermediate_path=pool_json_path,
        script_path=script_path,
        chapters_dir=chapters_dir,
        chapters_manifest_path=chapters_manifest_path,
        chapter_count=len({q.subelement for q in loaded_pool.questions}),
    )


def render_audio_from_chapter_manifest(
    manifest_path: Path,
    out_dir: Path,
    provider: str,
    model: str,
    voice: str,
    output_format: str,
    elevenlabs_output_format: str,
    elevenlabs_language_code: str,
    speed: float,
    instructions: str | None,
    merge_output: bool,
    embed_chapters: bool,
    out_manifest_path: Path | None = None,
    jobs: int = 1,
    unit_cache_dir: Path | None = None,
    progress_callback: Callable[[AudioRenderProgressUpdate], None] | None = None,
) -> AudioRenderSummary:
    normalized_provider = provider.strip().lower()
    client_factory: Callable[[], TtsClient]
    if normalized_provider == "openai":
        resolved_instructions = instructions.strip() if instructions else DEFAULT_TTS_INSTRUCTIONS
        render_fingerprint = (
            f"openai:{model}:{voice}:{speed}:{output_format}:{resolved_instructions}"
        )
        client = OpenAITtsClient(
            model=model,
            voice=voice,
            response_format=output_format,
            speed=speed,
            instructions=resolved_instructions,
        )
        
        def _openai_client_factory() -> TtsClient:
            return cast(
                TtsClient,
                OpenAITtsClient(
                model=model,
                voice=voice,
                response_format=output_format,
                speed=speed,
                instructions=resolved_instructions,
            ),
            )

        client_factory = _openai_client_factory
    elif normalized_provider == "elevenlabs":
        resolved_output_format = (
            elevenlabs_output_format.strip()
            if elevenlabs_output_format
            else DEFAULT_ELEVENLABS_OUTPUT_FORMAT
        )
        resolved_language_code = elevenlabs_language_code.strip() or "en"
        render_fingerprint = (
            "elevenlabs:"
            f"{model}:{voice}:{speed}:{resolved_output_format}:{resolved_language_code}"
        )
        client = ElevenLabsTtsClient(
            model=model,
            voice_id=voice,
            response_format=resolved_output_format,
            language_code=resolved_language_code,
            speed=speed,
        )
        
        def _elevenlabs_client_factory() -> TtsClient:
            return cast(
                TtsClient,
                ElevenLabsTtsClient(
                model=model,
                voice_id=voice,
                response_format=resolved_output_format,
                language_code=resolved_language_code,
                speed=speed,
            ),
            )

        client_factory = _elevenlabs_client_factory
    else:
        raise RuntimeError(f"Unsupported audio provider: {provider}")

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=out_dir,
        client=client,
        output_format=output_format,
        merge_output=merge_output,
        embed_chapters=embed_chapters,
        out_manifest_path=out_manifest_path,
        render_fingerprint=render_fingerprint,
        provider=normalized_provider,
        jobs=jobs,
        client_factory=client_factory,
        unit_cache_dir=unit_cache_dir,
        progress_callback=progress_callback,
    )
    return AudioRenderSummary(
        chapter_count=result.chapter_count,
        manifest_in_path=result.manifest_in_path,
        manifest_out_path=result.manifest_out_path,
        chapters_audio_dir=result.chapters_audio_dir,
        merged_audio_path=result.merged_audio_path,
        total_duration_seconds=result.total_duration_seconds,
        chapter_markers_embedded=result.chapter_markers_embedded,
        chapters_rendered=result.chapters_rendered,
        chapters_reused=result.chapters_reused,
    )


def verify_audio_outputs(
    manifest_path: Path,
    require_merged_audio: bool,
    require_chapter_markers: bool,
) -> AudioVerifySummary:
    return verify_audio_from_manifest(
        manifest_path=manifest_path,
        require_merged_audio=require_merged_audio,
        require_chapter_markers=require_chapter_markers,
    )
