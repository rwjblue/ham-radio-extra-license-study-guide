from __future__ import annotations

import base64
import binascii
import io
import json
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
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .facts import fact_sentence
from .intermediate import group_pool_questions
from .models import PoolMetadata, PoolQuestion, QuestionImage

QUESTION_ID_RE = re.compile(r"^([A-Z]\d[A-Z]\d{2}):\s*(.+)$")


def write_outputs(
    questions: list[PoolQuestion],
    out_dir: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None = None,
    image_root_dir: Path | None = None,
    txt_name: str = "extra_facts.txt",
    pdf_name: str = "extra_facts.pdf",
    dark_pdf_name: str | None = None,
) -> tuple[Path, Path, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = group_pool_questions(questions)

    txt_path = out_dir / txt_name
    _write_text(groups, txt_path, mode, omit_id, metadata)

    resolved_image_root = image_root_dir if image_root_dir is not None else out_dir

    pdf_path = out_dir / pdf_name
    _write_pdf(
        groups,
        pdf_path,
        mode,
        omit_id,
        metadata,
        image_root_dir=resolved_image_root,
        theme="light",
    )

    dark_pdf_path: Path | None = None
    if dark_pdf_name:
        dark_pdf_path = out_dir / dark_pdf_name
        _write_pdf(
            groups,
            dark_pdf_path,
            mode,
            omit_id,
            metadata,
            image_root_dir=resolved_image_root,
            theme="dark",
        )

    return txt_path, pdf_path, dark_pdf_path


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




def write_audio_script(
    questions: list[PoolQuestion],
    out_dir: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None = None,
    txt_name: str = "extra_facts_audio.txt",
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = group_pool_questions(questions)
    chapters = _build_audio_chapters(groups, mode=mode, omit_id=omit_id, metadata=metadata)

    chapters_dir = out_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    _write_chapter_texts(chapters, chapters_dir)

    manifest_path = out_dir / "audio_chapters_manifest.json"
    _write_chapter_manifest(chapters, chapters_dir, manifest_path)

    txt_path = out_dir / txt_name
    _write_combined_audio_text(chapters_dir, chapter_count=len(chapters), target=txt_path)
    return txt_path, chapters_dir, manifest_path


def _build_audio_chapters(
    groups: dict[str, list[PoolQuestion]],
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None,
) -> list[_AudioChapter]:
    chapters: list[_AudioChapter] = []
    chapter_lines: list[str] = []
    chapter_groups: list[str] = []
    current_subelement = ""
    seen_abbreviations: set[str] = set()
    chapter_title = ""

    for group, questions in groups.items():
        subelement = group[:2]
        if subelement != current_subelement:
            if current_subelement:
                chapter_lines.append(f"That wraps up chapter {current_subelement}.")
                chapters.append(
                    _AudioChapter(
                        code=current_subelement,
                        title=chapter_title,
                        groups=chapter_groups,
                        lines=chapter_lines,
                    )
                )
            chapter_title = _subelement_title_for_display(subelement, metadata)
            chapter_lines = _audio_chapter_intro(subelement, metadata)
            chapter_groups = []
            current_subelement = subelement

        chapter_groups.append(group)
        chapter_lines.append(_audio_group_intro(group, metadata))
        chapter_lines.append("")
        for question in questions:
            fact = fact_sentence(question, mode=mode, omit_id=omit_id)
            fact = _rewrite_first_abbreviation_use(fact, seen_abbreviations)
            fact = _expand_terms_for_tts(fact)
            chapter_lines.append(_normalize_audio_paragraph(fact))
            chapter_lines.append("")

    if current_subelement:
        chapter_lines.append(f"That wraps up chapter {current_subelement}.")
        chapters.append(
            _AudioChapter(
                code=current_subelement,
                title=chapter_title,
                groups=chapter_groups,
                lines=chapter_lines,
            )
        )

    return chapters


def _write_combined_audio_text(chapters_dir: Path, chapter_count: int, target: Path) -> None:
    lines: list[str] = []
    for number in range(1, chapter_count + 1):
        chapter_path = chapters_dir / _chapter_txt_name(number)
        chapter_lines = chapter_path.read_text(encoding="utf-8").splitlines()
        lines.extend(chapter_lines)
        lines.append("")
    lines.append("End of audio study guide.")
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_chapter_texts(chapters: list[_AudioChapter], chapters_dir: Path) -> None:
    for index, chapter in enumerate(chapters, start=1):
        chapter_path = chapters_dir / _chapter_txt_name(index)
        chapter_path.write_text("\n".join(chapter.lines).rstrip() + "\n", encoding="utf-8")


def _write_chapter_manifest(
    chapters: list[_AudioChapter],
    chapters_dir: Path,
    manifest_path: Path,
) -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "chapter_count": len(chapters),
        "chapters": [
            {
                "number": index,
                "code": chapter.code,
                "title": chapter.title or chapter.code,
                "groups": chapter.groups,
                "text_path": str((chapters_dir / _chapter_txt_name(index)).as_posix()),
            }
            for index, chapter in enumerate(chapters, start=1)
        ],
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _chapter_txt_name(number: int) -> str:
    return f"chapter-{number:02d}.txt"


def _audio_chapter_intro(subelement: str, metadata: PoolMetadata | None) -> list[str]:
    title = _subelement_title_for_display(subelement, metadata)
    if title:
        return [f"Chapter {subelement}: {title}.", ""]
    return [f"Chapter {subelement}.", ""]


def _audio_group_intro(group: str, metadata: PoolMetadata | None) -> str:
    _ = metadata
    return f"Section {group}."


def _rewrite_first_abbreviation_use(text: str, seen_abbreviations: set[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        abbreviation = match.group(1)
        expansion = match.group(2).strip()
        if abbreviation in seen_abbreviations:
            return abbreviation
        seen_abbreviations.add(abbreviation)
        return f"{expansion} ({abbreviation})"

    return re.sub(r"\b([A-Z]{2,})\s*\(([^)]+)\)", _replace, text)


def _expand_terms_for_tts(text: str) -> str:
    out = re.sub(r"\bkHz\b", "kilohertz", text)
    out = re.sub(r"\bMHz\b", "megahertz", out)
    out = re.sub(r"\bUSB\b", "upper side band", out)
    out = re.sub(r"\bLSB\b", "lower side band", out)
    out = re.sub(r"\bSSB\b", "single side band", out)
    return out


def _normalize_audio_paragraph(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _AudioChapter:
    def __init__(self, code: str, title: str, groups: list[str], lines: list[str]) -> None:
        self.code = code
        self.title = title
        self.groups = list(groups)
        self.lines = list(lines)

def _write_pdf(
    groups: dict[str, list[PoolQuestion]],
    target: Path,
    mode: str,
    omit_id: bool,
    metadata: PoolMetadata | None,
    image_root_dir: Path,
    theme: str = "light",
) -> None:
    palette = _pdf_palette(theme)

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
        fontSize=11,
        leading=14.5,
        textColor=palette["muted"],
        spaceAfter=8,
    )
    subelement_style = ParagraphStyle(
        "SubelementHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
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
        fontSize=12,
        leading=15,
        textColor=palette["group_heading"],
        spaceBefore=0,
        spaceAfter=0,
    )
    body = ParagraphStyle(
        "FactsBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11.5,
        leading=16.5,
        textColor=palette["ink"],
        spaceAfter=8,
        leftIndent=8,
        rightIndent=6,
    )
    note_style = ParagraphStyle(
        "FactsNote",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=13,
        textColor=palette["muted"],
        spaceAfter=10,
    )

    story: list[Flowable] = []
    story.extend(_cover_header(title_style, subtitle_style, mode, palette["line"]))
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
            image_flowables = _question_image_flowables(question, image_root_dir)
            story.append(_question_block(text, image_flowables, body, palette["line"]))
        story.append(Spacer(1, 0.07 * inch))

    doc = SimpleDocTemplate(
        str(target),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.65 * inch,
        title="FCC Amateur Extra Study Facts",
    )
    doc.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_footer(
            canvas,
            doc,
            palette["muted"],
            palette["page_bg"],
        ),
        onLaterPages=lambda canvas, doc: _draw_footer(
            canvas,
            doc,
            palette["muted"],
            palette["page_bg"],
        ),
    )


def _pdf_palette(theme: str) -> dict[str, colors.Color]:
    normalized = theme.strip().lower()
    if normalized == "dark":
        return {
            "ink": colors.HexColor("#E5E7EB"),
            "muted": colors.HexColor("#9CA3AF"),
            "accent": colors.HexColor("#14B8A6"),
            "group_heading": colors.HexColor("#5EEAD4"),
            "group_bg": colors.HexColor("#111827"),
            "line": colors.HexColor("#374151"),
            "page_bg": colors.HexColor("#030712"),
        }
    return {
        "ink": colors.HexColor("#1F2937"),
        "muted": colors.HexColor("#4B5563"),
        "accent": colors.HexColor("#0F766E"),
        "group_heading": colors.HexColor("#0F766E"),
        "group_bg": colors.HexColor("#F8FAFC"),
        "line": colors.HexColor("#CBD5E1"),
        "page_bg": colors.white,
    }

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
    line_color: colors.Color,
) -> list[Flowable]:
    return [
        Paragraph("FCC Amateur Extra (Element 4) Statements of Fact", title_style),
        Paragraph(
            f"{_mode_label(mode)} · Grouped by subelement and question group",
            subtitle_style,
        ),
        HRFlowable(width="100%", color=line_color, thickness=1.2),
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


def _question_block(
    text: str,
    image_flowables: list[Flowable],
    style: ParagraphStyle,
    line: colors.Color,
) -> KeepTogether:
    formatted = _format_pdf_fact(text)
    fact = Paragraph(formatted, style)
    bottom_rule = HRFlowable(width="100%", color=line, thickness=0.5, spaceBefore=1, spaceAfter=4)
    if not image_flowables:
        return KeepTogether([fact, bottom_rule])
    top_rule = HRFlowable(width="100%", color=line, thickness=0.5, spaceBefore=1, spaceAfter=4)
    return KeepTogether([top_rule, *image_flowables, fact, bottom_rule])


def _format_pdf_fact(text: str) -> str:
    match = QUESTION_ID_RE.match(text)
    if match is None:
        return text
    question_id, remainder = match.groups()
    return f"<b>{question_id}:</b> {remainder}"


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


def _draw_footer(
    canvas: Canvas,
    doc: BaseDocTemplate,
    color: colors.Color,
    page_background: colors.Color,
) -> None:
    page_canvas = canvas
    page_canvas.saveState()
    page_canvas.setFillColor(page_background)
    page_canvas.rect(0, 0, LETTER[0], LETTER[1], stroke=0, fill=1)
    page_canvas.setFont("Helvetica", 8.5)
    page_canvas.setFillColor(color)
    page_canvas.drawString(doc.leftMargin, 0.4 * inch, "FCC Amateur Extra Study Facts")
    page_canvas.drawRightString(
        LETTER[0] - doc.rightMargin,
        0.4 * inch,
        f"Page {doc.page}",
    )
    page_canvas.restoreState()


def _question_image_flowables(question: PoolQuestion, root_dir: Path) -> list[Flowable]:
    flowables: list[Flowable] = []
    seen_paths: set[str] = set()

    for image in question.images:
        embedded_bytes = _embedded_image_bytes(image)
        if embedded_bytes is not None:
            flowables.append(_pdf_image(embedded_bytes))
            flowables.append(Spacer(1, 0.05 * inch))
            continue
        if image.path is None:
            continue
        normalized_path = image.path.strip()
        if not normalized_path or normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        resolved = root_dir / normalized_path
        if not resolved.exists():
            continue
        flowables.append(_pdf_image(resolved))
        flowables.append(Spacer(1, 0.05 * inch))

    for image_path in question.image_paths:
        normalized_path = image_path.strip()
        if not normalized_path or normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        resolved = root_dir / normalized_path
        if not resolved.exists():
            continue
        flowables.append(_pdf_image(resolved))
        flowables.append(Spacer(1, 0.05 * inch))
    return flowables


def _pdf_image(source: Path | bytes) -> Image:
    image = Image(str(source)) if isinstance(source, Path) else Image(io.BytesIO(source))
    max_width = 5.6 * inch
    max_height = 2.8 * inch
    width = float(image.imageWidth)
    height = float(image.imageHeight)
    if width > 0 and height > 0:
        scale = min(max_width / width, max_height / height, 1.0)
        image.drawWidth = width * scale
        image.drawHeight = height * scale
    return image


def _embedded_image_bytes(image: QuestionImage) -> bytes | None:
    if image.data_base64:
        return _decode_base64_bytes(image.data_base64)
    if image.data_url:
        return _decode_data_url_bytes(image.data_url)
    return None


def _decode_data_url_bytes(value: str) -> bytes | None:
    match = re.match(r"^data:[^;]+;base64,(.+)$", value.strip(), flags=re.IGNORECASE | re.DOTALL)
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
