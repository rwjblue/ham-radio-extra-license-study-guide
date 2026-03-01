from __future__ import annotations

from pathlib import Path
from typing import Any, cast


def extract_text(source_path: Path) -> str:
    """Extract source text. Uses DOCX extractor for .docx, PDF for .pdf."""
    suffix = source_path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx(source_path)
    if suffix == ".pdf":
        try:
            return _extract_pdfplumber(source_path)
        except Exception:
            return _extract_pymupdf(source_path)
    raise ValueError(f"Unsupported source type: {source_path}")


def _extract_docx(source_path: Path) -> str:
    from docx import Document

    document = Document(str(source_path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


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
