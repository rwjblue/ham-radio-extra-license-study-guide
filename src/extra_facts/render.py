from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .facts import fact_sentence
from .intermediate import group_pool_questions
from .models import PoolMetadata, PoolQuestion

QUESTION_ID_RE = re.compile(r"^([A-Z]\d[A-Z]\d{2}):\s*(.+)$")


def write_outputs(
    questions: list[PoolQuestion],
    out_dir: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None = None,
    txt_name: str = "extra_facts.txt",
    pdf_name: str = "extra_facts.pdf",
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = group_pool_questions(questions)

    txt_path = out_dir / txt_name
    _write_text(groups, txt_path, mode, omit_id, metadata)

    pdf_path = out_dir / pdf_name
    _write_pdf(groups, pdf_path, mode, omit_id, metadata)

    return txt_path, pdf_path


def _write_text(
    groups: dict[str, list[PoolQuestion]],
    target: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None,
) -> None:
    lines: list[str] = []
    current_subelement = ""

    for group, questions in groups.items():
        subelement = group[:2]
        if subelement != current_subelement:
            if lines:
                lines.append("")
            subelement_title = _subelement_heading(subelement, metadata)
            lines.append(f"## {subelement_title}")
            current_subelement = subelement

        group_title = _group_heading_text(group, metadata)
        lines.append(f"### {group_title}")
        for question in questions:
            lines.append(fact_sentence(question, mode=mode, omit_id=omit_id))
        lines.append("")

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_pdf(
    groups: dict[str, list[PoolQuestion]],
    target: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None,
) -> None:
    palette = {
        "ink": colors.HexColor("#1F2937"),
        "muted": colors.HexColor("#4B5563"),
        "accent": colors.HexColor("#0F766E"),
        "accent_soft": colors.HexColor("#ECFEFF"),
        "group_bg": colors.HexColor("#F8FAFC"),
        "line": colors.HexColor("#CBD5E1"),
    }

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FactsTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=palette["ink"],
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "FactsSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=palette["muted"],
        spaceAfter=8,
    )
    subelement_style = ParagraphStyle(
        "SubelementHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.white,
        leftIndent=6,
        rightIndent=6,
        spaceBefore=0,
        spaceAfter=0,
    )
    group_style = ParagraphStyle(
        "GroupHeading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=palette["accent"],
        spaceBefore=0,
        spaceAfter=0,
    )
    body = ParagraphStyle(
        "FactsBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=15,
        textColor=palette["ink"],
        spaceAfter=7,
        leftIndent=8,
        rightIndent=6,
    )
    note_style = ParagraphStyle(
        "FactsNote",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor=palette["muted"],
        spaceAfter=10,
    )

    story: list[Flowable] = []
    story.extend(_cover_header(title_style, subtitle_style, mode))
    story.append(
        Paragraph(
            "Workbook format: review each statement, speak it aloud, and mark weak items.",
            note_style,
        )
    )
    seen_subelement = ""

    for group, questions in groups.items():
        subelement = group[:2]
        if subelement != seen_subelement:
            story.append(Spacer(1, 0.08 * inch))
            story.append(
                _subelement_banner(
                    _subelement_heading(subelement, metadata),
                    subelement_style,
                    palette["accent"],
                )
            )
            seen_subelement = subelement

        story.append(Spacer(1, 0.07 * inch))
        story.append(
            _group_heading(
                _group_heading_text(group, metadata),
                group_style,
                palette["group_bg"],
                palette["line"],
            )
        )
        story.append(Spacer(1, 0.02 * inch))
        for question in questions:
            text = fact_sentence(question, mode=mode, omit_id=omit_id)
            story.append(_fact_item(text, body, palette["line"]))
        story.append(Spacer(1, 0.07 * inch))

    doc = SimpleDocTemplate(
        str(target),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.65 * inch,
        title="FCC Amateur Extra Study Facts",
    )
    doc.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_footer(canvas, doc, palette["muted"]),
        onLaterPages=lambda canvas, doc: _draw_footer(canvas, doc, palette["muted"]),
    )


def _mode_label(mode: str) -> str:
    if mode == "prose":
        return "LLM prose study guide"
    if mode == "tts":
        return "TTS-optimized study guide"
    return "Literal study guide"


def _cover_header(
    title_style: ParagraphStyle,
    subtitle_style: ParagraphStyle,
    mode: str,
) -> list[Flowable]:
    return [
        Paragraph("FCC Amateur Extra (Element 4) Statements of Fact", title_style),
        Paragraph(
            f"{_mode_label(mode)} · Grouped by subelement and question group",
            subtitle_style,
        ),
        HRFlowable(width="100%", color=colors.HexColor("#CBD5E1"), thickness=1.2),
        Spacer(1, 0.08 * inch),
    ]


def _subelement_banner(
    label: str,
    style: ParagraphStyle,
    accent: colors.Color,
) -> Table:
    table = Table([[Paragraph(label, style)]], colWidths=[7.1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _group_heading(
    label_text: str,
    style: ParagraphStyle,
    background: colors.Color,
    line: colors.Color,
) -> KeepTogether:
    label = Table([[Paragraph(label_text, style)]], colWidths=[7.1 * inch])
    label.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return KeepTogether([label])


def _fact_item(text: str, style: ParagraphStyle, line: colors.Color) -> KeepTogether:
    formatted = _format_pdf_fact(text)
    fact = Paragraph(formatted, style)
    rule = HRFlowable(width="100%", color=line, thickness=0.5, spaceBefore=1, spaceAfter=4)
    return KeepTogether([fact, rule])


def _format_pdf_fact(text: str) -> str:
    match = QUESTION_ID_RE.match(text)
    if match is None:
        return text
    question_id, remainder = match.groups()
    return f"<b>{question_id}:</b> {remainder}"


def _subelement_heading(subelement: str, metadata: PoolMetadata | None) -> str:
    if metadata is None:
        return f"SUBELEMENT {subelement}"
    title = metadata.subelement_titles.get(subelement)
    if not title:
        return f"SUBELEMENT {subelement}"
    return f"SUBELEMENT {subelement} - {title}"


def _group_heading_text(group: str, metadata: PoolMetadata | None) -> str:
    if metadata is None:
        return f"Group {group}"
    title = metadata.group_titles.get(group)
    if not title:
        return f"Group {group}"
    return f"Group {group} - {title}"


def _draw_footer(canvas: Canvas, doc: BaseDocTemplate, color: colors.Color) -> None:
    page_canvas = canvas
    page_canvas.saveState()
    page_canvas.setFont("Helvetica", 8.5)
    page_canvas.setFillColor(color)
    page_canvas.drawString(doc.leftMargin, 0.4 * inch, "FCC Amateur Extra Study Facts")
    page_canvas.drawRightString(
        LETTER[0] - doc.rightMargin,
        0.4 * inch,
        f"Page {doc.page}",
    )
    page_canvas.restoreState()
