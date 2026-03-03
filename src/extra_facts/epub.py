# pyright: reportUnknownMemberType=false
from __future__ import annotations

import base64
import binascii
import mimetypes
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ebooklib import epub  # type: ignore[import-untyped]

from .facts import fact_sentence
from .intermediate import group_pool_questions
from .models import PoolMetadata, PoolQuestion, QuestionImage
from .repro import deterministic_utc_datetime

QUESTION_ID_RE = re.compile(r"^([A-Z]\d[A-Z]\d{2}):\s*(.+)$")
QA_PAIR_RE = re.compile(r"^Q:\s*(.+?)\s+A:\s*(.+)$")


def write_epub(
    questions: list[PoolQuestion],
    target: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None = None,
    image_root_dir: Path | None = None,
) -> Path:
    generated_at = deterministic_utc_datetime()
    book = epub.EpubBook()
    book.set_identifier("fcc-amateur-extra-study-facts")
    book.set_title("FCC Amateur Extra (Element 4) Statements of Fact")
    book.set_language("en")

    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=_default_css().encode("utf-8"),
    )
    book.add_item(style)

    groups = group_pool_questions(questions)
    image_registry: dict[str, str] = {}

    chapters: list[epub.EpubHtml] = []
    current_subelement = ""
    subelement_groups: dict[str, list[PoolQuestion]] = {}

    for group, group_questions in groups.items():
        subelement = group[:2]
        if subelement != current_subelement:
            if current_subelement and subelement_groups:
                chapter = _build_chapter(
                    current_subelement,
                    subelement_groups,
                    mode,
                    omit_id,
                    metadata,
                    image_root_dir,
                    book,
                    image_registry,
                )
                chapter.add_item(style)
                book.add_item(chapter)
                chapters.append(chapter)
            current_subelement = subelement
            subelement_groups = {}
        subelement_groups[group] = group_questions

    if current_subelement and subelement_groups:
        chapter = _build_chapter(
            current_subelement,
            subelement_groups,
            mode,
            omit_id,
            metadata,
            image_root_dir,
            book,
            image_registry,
        )
        chapter.add_item(style)
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    target.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(target), book, options={"mtime": generated_at})
    _normalize_zip_timestamps(target, generated_at)
    return target


def _normalize_zip_timestamps(target: Path, generated_at: datetime) -> None:
    fixed_date_time: tuple[int, int, int, int, int, int] = (
        generated_at.year,
        generated_at.month,
        generated_at.day,
        generated_at.hour,
        generated_at.minute,
        generated_at.second,
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with zipfile.ZipFile(target, "r") as source, zipfile.ZipFile(temp_path, "w") as out:
            for source_info in source.infolist():
                normalized = zipfile.ZipInfo(source_info.filename, date_time=fixed_date_time)
                normalized.compress_type = source_info.compress_type
                normalized.external_attr = source_info.external_attr
                normalized.comment = source_info.comment
                normalized.extra = source_info.extra
                normalized.create_system = source_info.create_system
                normalized.create_version = source_info.create_version
                normalized.extract_version = source_info.extract_version
                normalized.flag_bits = source_info.flag_bits
                out.writestr(normalized, source.read(source_info.filename))
        temp_path.replace(target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _build_chapter(
    subelement: str,
    groups: dict[str, list[PoolQuestion]],
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None,
    image_root_dir: Path | None,
    book: Any,
    image_registry: dict[str, str],
) -> epub.EpubHtml:
    title = _subelement_heading(subelement, metadata)
    chapter = epub.EpubHtml(
        title=title,
        file_name=f"chapter_{subelement.lower()}.xhtml",
        lang="en",
    )

    html_parts: list[str] = []
    html_parts.append(f"<h1>{_escape(title)}</h1>")

    for group, questions in groups.items():
        group_title = _group_heading_text(group, metadata)
        html_parts.append(f"<h2>{_escape(group_title)}</h2>")

        for question in questions:
            text = fact_sentence(question, mode=mode, omit_id=omit_id)
            image_tags = _question_image_html(
                question, image_root_dir, book, image_registry
            )
            html_parts.append('<div class="question">')
            for tag in image_tags:
                html_parts.append(tag)
            html_parts.extend(_question_html_lines(text))
            html_parts.append("</div>")

    chapter.content = "\n".join(html_parts).encode("utf-8")
    return chapter


def _question_html_lines(text: str) -> list[str]:
    question_id, body = _split_question_id_and_body(text)
    qa_parts = _split_qa_pair(body)
    if qa_parts is None:
        if question_id is None:
            return [f"<p>{_escape(body)}</p>"]
        return [f"<p><strong>{_escape(question_id)}:</strong> {_escape(body)}</p>"]

    question_text, answer_text = qa_parts
    lines: list[str] = []
    if question_id is not None:
        lines.append(f'<p class="question-id">{_escape(question_id)}</p>')
    question_markup = (
        '<p class="qa-line qa-question"><span class="qa-label">Q:</span> '
        f"{_escape(question_text)}</p>"
    )
    answer_markup = (
        '<p class="qa-line qa-answer"><span class="qa-label">A:</span> '
        f"{_escape(answer_text)}</p>"
    )
    lines.append(question_markup)
    lines.append(answer_markup)
    return lines


def _split_question_id_and_body(text: str) -> tuple[str | None, str]:
    match = QUESTION_ID_RE.match(text)
    if match is None:
        return None, text
    return match.group(1), match.group(2)


def _split_qa_pair(text: str) -> tuple[str, str] | None:
    match = QA_PAIR_RE.match(text.strip())
    if match is None:
        return None
    question_text = match.group(1).strip()
    answer_text = match.group(2).strip()
    return question_text, answer_text


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _question_image_html(
    question: PoolQuestion,
    root_dir: Path | None,
    book: Any,
    image_registry: dict[str, str],
) -> list[str]:
    tags: list[str] = []
    seen_paths: set[str] = set()

    for image in question.images:
        embedded = _embedded_image_bytes(image)
        if embedded is not None:
            media_type = image.media_type or "image/png"
            ext = _extension_for_media_type(media_type)
            file_name = f"images/{question.question_id.lower()}-embedded-{len(image_registry)}{ext}"
            if file_name not in image_registry:
                epub_image = epub.EpubImage()
                epub_image.file_name = file_name
                epub_image.media_type = media_type
                epub_image.content = embedded
                book.add_item(epub_image)
                image_registry[file_name] = file_name
            tags.append(f'<div class="figure"><img src="{file_name}" alt="Figure" /></div>')
            continue
        if image.path is None:
            continue
        tag = _file_image_tag(image.path, root_dir, question, book, image_registry, seen_paths)
        if tag:
            tags.append(tag)

    for image_path in question.image_paths:
        tag = _file_image_tag(image_path, root_dir, question, book, image_registry, seen_paths)
        if tag:
            tags.append(tag)

    return tags


def _file_image_tag(
    raw_path: str,
    root_dir: Path | None,
    question: PoolQuestion,
    book: Any,
    image_registry: dict[str, str],
    seen_paths: set[str],
) -> str | None:
    normalized = raw_path.strip()
    if not normalized or normalized in seen_paths:
        return None
    seen_paths.add(normalized)
    if root_dir is None:
        return None
    resolved = root_dir / normalized
    if not resolved.exists():
        return None
    media_type = mimetypes.guess_type(str(resolved))[0] or "image/png"
    file_name = f"images/{normalized}"
    if file_name not in image_registry:
        epub_image = epub.EpubImage()
        epub_image.file_name = file_name
        epub_image.media_type = media_type
        epub_image.content = resolved.read_bytes()
        book.add_item(epub_image)
        image_registry[file_name] = file_name
    alt = f"Figure for {_escape(question.question_id)}"
    return f'<div class="figure"><img src="{file_name}" alt="{alt}" /></div>'


def _embedded_image_bytes(image: QuestionImage) -> bytes | None:
    if image.data_base64:
        return _decode_base64_bytes(image.data_base64)
    if image.data_url:
        return _decode_data_url_bytes(image.data_url)
    return None


def _decode_data_url_bytes(value: str) -> bytes | None:
    match = re.match(
        r"^data:[^;]+;base64,(.+)$", value.strip(), flags=re.IGNORECASE | re.DOTALL
    )
    if match is None:
        return None
    return _decode_base64_bytes(match.group(1))


def _decode_base64_bytes(value: str) -> bytes | None:
    normalized = re.sub(r"\s+", "", value)
    if not normalized:
        return None
    try:
        return base64.b64decode(normalized, validate=True)
    except binascii.Error:
        return None


def _extension_for_media_type(media_type: str) -> str:
    ext = mimetypes.guess_extension(media_type)
    if ext:
        return ext
    return ".png"


def _subelement_heading(subelement: str, metadata: PoolMetadata | None) -> str:
    title = _subelement_title_for_display(subelement, metadata)
    if not title:
        return f"SUBELEMENT {subelement}"
    return f"SUBELEMENT {subelement} - {title}"


def _group_heading_text(group: str, metadata: PoolMetadata | None) -> str:
    title = _group_title_for_display(group, metadata)
    if not title:
        return f"Group {group}"
    return f"Group {group} - {title}"


def _subelement_title_for_display(subelement: str, metadata: PoolMetadata | None) -> str:
    if metadata is None:
        return ""
    friendly = metadata.subelement_friendly_titles.get(subelement, "").strip()
    if friendly:
        return friendly
    return metadata.subelement_titles.get(subelement, "").strip()


def _group_title_for_display(group: str, metadata: PoolMetadata | None) -> str:
    if metadata is None:
        return ""
    friendly = metadata.group_friendly_titles.get(group, "").strip()
    if friendly:
        return friendly
    return metadata.group_titles.get(group, "").strip()


def _default_css() -> str:
    return """\
body {
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.6;
    margin: 1em;
    color: #1F2937;
}
h1 {
    font-size: 1.4em;
    border-bottom: 2px solid #0F766E;
    padding-bottom: 0.3em;
    color: #0F766E;
}
h2 {
    font-size: 1.1em;
    color: #0F766E;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}
.question {
    margin-bottom: 0.8em;
    padding-bottom: 0.5em;
    border-bottom: 1px solid #E5E7EB;
}
.question p {
    margin: 0.3em 0;
}
.question-id {
    font-size: 0.84em;
    color: #6B7280;
    margin-bottom: 0.05em;
}
.qa-line {
    margin: 0.1em 0;
}
.qa-answer {
    margin-left: 0;
}
.qa-label {
    font-weight: 700;
}
.figure {
    text-align: center;
    margin: 0.5em 0;
}
.figure img {
    max-width: 100%;
}
"""
