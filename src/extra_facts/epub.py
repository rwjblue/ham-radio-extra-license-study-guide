# pyright: reportUnknownMemberType=false
from __future__ import annotations

import base64
import binascii
import mimetypes
import re
from pathlib import Path
from typing import Any

from ebooklib import epub  # type: ignore[import-untyped]

from .facts import fact_sentence
from .intermediate import group_pool_questions
from .models import PoolMetadata, PoolQuestion, QuestionImage

QUESTION_ID_RE = re.compile(r"^([A-Z]\d[A-Z]\d{2}):\s*(.+)$")


def write_epub(
    questions: list[PoolQuestion],
    target: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None = None,
    image_root_dir: Path | None = None,
) -> Path:
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
    epub.write_epub(str(target), book)
    return target


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
            formatted = _format_fact_html(text)
            image_tags = _question_image_html(
                question, image_root_dir, book, image_registry
            )
            html_parts.append('<div class="question">')
            for tag in image_tags:
                html_parts.append(tag)
            html_parts.append(f"<p>{formatted}</p>")
            html_parts.append("</div>")

    chapter.content = "\n".join(html_parts).encode("utf-8")
    return chapter


def _format_fact_html(text: str) -> str:
    escaped = _escape(text)
    match = QUESTION_ID_RE.match(text)
    if match is None:
        return escaped
    question_id, remainder = match.groups()
    return f"<strong>{_escape(question_id)}:</strong> {_escape(remainder)}"


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
.figure {
    text-align: center;
    margin: 0.5em 0;
}
.figure img {
    max-width: 100%;
}
"""
