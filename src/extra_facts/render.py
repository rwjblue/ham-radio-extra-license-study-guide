from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from .facts import fact_sentence
from .intermediate import group_pool_questions
from .models import PoolQuestion


def write_outputs(
    questions: list[PoolQuestion],
    out_dir: Path,
    mode: str,
    omit_id: bool,
    txt_name: str = "extra_facts.txt",
    pdf_name: str = "extra_facts.pdf",
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = group_pool_questions(questions)

    txt_path = out_dir / txt_name
    _write_text(groups, txt_path, mode, omit_id)

    pdf_path = out_dir / pdf_name
    _write_pdf(groups, pdf_path, mode, omit_id)

    return txt_path, pdf_path


def _write_text(
    groups: dict[str, list[PoolQuestion]],
    target: Path,
    mode: str,
    omit_id: bool,
) -> None:
    lines: list[str] = []
    current_subelement = ""

    for group, questions in groups.items():
        subelement = group[:2]
        if subelement != current_subelement:
            if lines:
                lines.append("")
            lines.append(f"## {subelement}")
            current_subelement = subelement

        lines.append(f"### {group}")
        for question in questions:
            lines.append(fact_sentence(question, mode=mode, omit_id=omit_id))
        lines.append("")

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_pdf(
    groups: dict[str, list[PoolQuestion]],
    target: Path,
    mode: str,
    omit_id: bool,
) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "FactsBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        spaceAfter=4,
    )
    group_style = ParagraphStyle(
        "GroupHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        spaceBefore=10,
        spaceAfter=6,
    )
    subelement_style = ParagraphStyle(
        "SubHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceBefore=14,
        spaceAfter=8,
    )

    story: list[Flowable] = []
    seen_subelement = ""

    for group, questions in groups.items():
        subelement = group[:2]
        if subelement != seen_subelement:
            story.append(Paragraph(f"Subelement {subelement}", subelement_style))
            seen_subelement = subelement

        story.append(Paragraph(f"Group {group}", group_style))
        for question in questions:
            text = fact_sentence(question, mode=mode, omit_id=omit_id)
            story.append(Paragraph(text, body))
        story.append(Spacer(1, 0.08 * inch))

    doc = SimpleDocTemplate(
        str(target),
        pagesize=LETTER,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title="FCC Amateur Extra Study Facts",
    )
    doc.build(story)
