from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from zipfile import ZipInfo


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
    from docx import Document

    document = Document(str(source_path))
    lines: list[str] = []
    question_image_paths: dict[str, list[str]] = {}
    current_question_id: str | None = None

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)
            question_id = _extract_question_id(text)
            if question_id is not None:
                current_question_id = question_id

        if current_question_id is None:
            continue

        image_paths = _collect_paragraph_image_paths(paragraph)
        if not image_paths:
            continue

        mapped_paths = question_image_paths.setdefault(current_question_id, [])
        for image_path in image_paths:
            if image_path not in mapped_paths:
                mapped_paths.append(image_path)

    return "\n".join(lines), question_image_paths


def export_docx_media(source_path: Path, assets_dir: Path) -> dict[str, str]:
    """Export DOCX embedded media files into assets_dir."""
    import zipfile

    assets_dir.mkdir(parents=True, exist_ok=True)
    media_map: dict[str, str] = {}

    with zipfile.ZipFile(source_path) as archive:
        media_entries: list[ZipInfo] = sorted(
            [
                item
                for item in archive.infolist()
                if item.filename.startswith("word/media/") and not item.is_dir()
            ],
            key=lambda item: item.filename,
        )

        for entry in media_entries:
            name = Path(entry.filename).name
            target = assets_dir / name
            target.write_bytes(archive.read(entry.filename))
            media_map[entry.filename] = str(Path(assets_dir.name) / name)

    return media_map


def _collect_paragraph_image_paths(paragraph: Any) -> list[str]:
    image_paths: list[str] = []

    blip_elements = paragraph._p.xpath('.//a:blip[@r:embed]')
    for blip in blip_elements:
        rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if not rel_id:
            continue

        rel = paragraph.part.rels.get(rel_id)
        if rel is None:
            continue

        partname = getattr(rel.target_part, "partname", None)
        if partname is None:
            continue

        image_path = str(partname).lstrip("/")
        if image_path.startswith("word/media/"):
            image_paths.append(image_path)

    return image_paths


def _extract_question_id(line: str) -> str | None:
    if len(line) < 6:
        return None
    prefix = line[:6]
    if (
        prefix[0] == "E"
        and prefix[1].isdigit()
        and prefix[2].isalpha()
        and prefix[3:5].isdigit()
    ):
        return prefix
    return None


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
