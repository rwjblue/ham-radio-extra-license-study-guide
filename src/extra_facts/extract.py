from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

DOCX_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}
REL_NS = {
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
QUESTION_ID_PREFIX_RE = re.compile(r"^(E\d[A-Z]\d{2})\b")
FIGURE_REF_RE = re.compile(r"\bFigure\s+(E\d-\d+)\b", re.IGNORECASE)
POOL_END_RE = re.compile(r"end of question pool text", re.IGNORECASE)


def extract_text(source_path: Path) -> str:
    """Extract source text. Uses DOCX extractor for .docx, PDF for .pdf."""
    suffix = source_path.suffix.lower()
    if suffix == ".docx":
        text, _ = extract_docx_with_images(source_path)
        return text
    if suffix == ".pdf":
        try:
            return _extract_pdfplumber(source_path)
        except Exception:
            return _extract_pymupdf(source_path)
    raise ValueError(f"Unsupported source type: {source_path}")


def extract_docx_with_images(source_path: Path) -> tuple[str, dict[str, list[str]]]:
    """Extract normalized DOCX text and question-to-image relationships."""
    document_root = _read_docx_document_xml(source_path)
    relationship_targets = _read_docx_relationships(source_path)
    lines: list[str] = []
    question_image_paths: dict[str, list[str]] = {}
    ordered_image_paths: list[str] = []
    current_question_id: str | None = None

    for paragraph in document_root.findall(".//w:body//w:p", DOCX_NS):
        text = _paragraph_text(paragraph).strip()
        if text:
            lines.append(text)
            question_id = _extract_question_id(text)
            if question_id is not None:
                current_question_id = question_id
            if POOL_END_RE.search(text):
                current_question_id = None

        image_paths = _collect_paragraph_image_paths(
            paragraph,
            relationship_targets=relationship_targets,
        )
        if not image_paths:
            continue
        for image_path in image_paths:
            if image_path not in ordered_image_paths:
                ordered_image_paths.append(image_path)

        if current_question_id is None:
            continue

        mapped_paths = question_image_paths.setdefault(current_question_id, [])
        for image_path in image_paths:
            if image_path not in mapped_paths:
                mapped_paths.append(image_path)

    raw_text = "\n".join(lines)
    question_image_paths = _merge_question_image_paths(
        question_image_paths,
        _map_images_from_figure_references(raw_text, ordered_image_paths),
    )
    return raw_text, question_image_paths


def export_docx_media(source_path: Path, assets_dir: Path) -> dict[str, str]:
    """Export DOCX embedded media files into assets_dir."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    media_map: dict[str, str] = {}
    for media_path, payload in _read_docx_media(source_path).items():
        name = Path(media_path).name
        target = assets_dir / name
        target.write_bytes(payload)
        media_map[media_path] = str(Path(assets_dir.name) / name)

    return media_map


def export_docx_media_for_questions(
    source_path: Path,
    assets_dir: Path,
    question_images: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Export media using per-question filenames like e1a04-01.png."""
    media_bytes = _read_docx_media(source_path)
    assets_dir.mkdir(parents=True, exist_ok=True)

    question_assets: dict[str, list[str]] = {}
    for question_id, image_paths in question_images.items():
        mapped_paths: list[str] = []
        for index, image_path in enumerate(image_paths, start=1):
            payload = media_bytes.get(image_path)
            if payload is None:
                continue
            suffix = Path(image_path).suffix.lower() or ".bin"
            filename = f"{question_id.lower()}-{index:02d}{suffix}"
            target = assets_dir / filename
            target.write_bytes(payload)
            mapped_paths.append(str(Path(assets_dir.name) / filename))
        if mapped_paths:
            question_assets[question_id] = mapped_paths

    return question_assets


def _read_docx_media(source_path: Path) -> dict[str, bytes]:
    import zipfile

    media_bytes: dict[str, bytes] = {}
    with zipfile.ZipFile(source_path) as archive:
        media_entries = sorted(
            [
                item
                for item in archive.infolist()
                if item.filename.startswith("word/media/") and not item.is_dir()
            ],
            key=lambda item: item.filename,
        )
        for entry in media_entries:
            media_bytes[entry.filename] = archive.read(entry.filename)
    return media_bytes


def _read_docx_document_xml(source_path: Path) -> ET.Element:
    import zipfile

    with zipfile.ZipFile(source_path) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def _read_docx_relationships(source_path: Path) -> dict[str, str]:
    import zipfile

    with zipfile.ZipFile(source_path) as archive:
        try:
            rels_root = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        except KeyError:
            return {}

    relationship_targets: dict[str, str] = {}
    for rel in rels_root.findall("pr:Relationship", REL_NS):
        rel_id = rel.get("Id")
        target = rel.get("Target")
        if not rel_id or not target:
            continue
        normalized = target.lstrip("/")
        if not target.startswith("/"):
            normalized = posixpath.normpath(posixpath.join("word", normalized))
        if normalized.startswith("word/media/"):
            relationship_targets[rel_id] = normalized
    return relationship_targets


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(text for text in paragraph.itertext() if text)


def _collect_paragraph_image_paths(
    paragraph: ET.Element,
    relationship_targets: dict[str, str],
) -> list[str]:
    image_paths: list[str] = []

    blip_elements = paragraph.findall(".//a:blip", DOCX_NS)
    for blip in blip_elements:
        rel_id = blip.get(f"{{{DOCX_NS['r']}}}embed")
        if not rel_id:
            continue

        image_path = relationship_targets.get(rel_id)
        if image_path:
            image_paths.append(image_path)

    return image_paths


def _extract_question_id(line: str) -> str | None:
    match = QUESTION_ID_PREFIX_RE.match(line)
    if match is None:
        return None
    return match.group(1)


def _merge_question_image_paths(
    base: dict[str, list[str]],
    additional: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {key: list(value) for key, value in base.items()}
    for question_id, image_paths in additional.items():
        existing = merged.setdefault(question_id, [])
        for image_path in image_paths:
            if image_path not in existing:
                existing.append(image_path)
    return merged


def _map_images_from_figure_references(
    raw_text: str,
    ordered_image_paths: list[str],
) -> dict[str, list[str]]:
    if not ordered_image_paths:
        return {}

    from .parser import parse_questions

    questions, _ = parse_questions(raw_text)
    ordered_figures: list[str] = []
    figure_questions: dict[str, list[str]] = {}
    for question in questions:
        refs = _question_figure_refs(question.question_text, question.choices.values())
        for figure in refs:
            if figure not in ordered_figures:
                ordered_figures.append(figure)
            figure_questions.setdefault(figure, []).append(question.question_id)

    if not ordered_figures or len(ordered_figures) != len(ordered_image_paths):
        return {}

    figure_image_path = {
        figure: image_path
        for figure, image_path in zip(ordered_figures, ordered_image_paths, strict=True)
    }
    mapped: dict[str, list[str]] = {}
    for figure, question_ids in figure_questions.items():
        image_path = figure_image_path.get(figure)
        if image_path is None:
            continue
        for question_id in question_ids:
            mapped.setdefault(question_id, []).append(image_path)
    return mapped


def _question_figure_refs(question_text: str, choices: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    for text in [question_text, *choices]:
        for match in FIGURE_REF_RE.finditer(text):
            figure = match.group(1).upper()
            if figure not in ordered:
                ordered.append(figure)
    return ordered


def _extract_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
    return "\n".join(pages)


def _extract_pymupdf(pdf_path: Path) -> str:
    import fitz

    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = cast(Any, page).get_text("text")
            if isinstance(text, str):
                parts.append(text)
            else:
                parts.append(str(text))
    return "\n".join(parts)
