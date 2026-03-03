from __future__ import annotations

import base64
import zipfile
from pathlib import Path

from extra_facts.build import build_from_pool_json
from extra_facts.epub import _question_html_lines, write_epub  # pyright: ignore[reportPrivateUsage]
from extra_facts.intermediate import write_question_pool
from extra_facts.models import (
    LlmProse,
    PoolMetadata,
    PoolQuestion,
    ProseValidation,
    QuestionImage,
    QuestionPool,
)

PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W6mQAAAAASUVORK5CYII="
)


def _sample_pool(
    questions: list[PoolQuestion] | None = None,
    metadata: PoolMetadata | None = None,
) -> QuestionPool:
    if questions is None:
        questions = [
            PoolQuestion(
                question_id="E1A01",
                question_text="What is one purpose of the Amateur Radio Service?",
                choices=["Advance the art", "Entertainment", "Advertising", "None"],
                correct_choice_index=0,
                group="E1A",
                subelement="E1",
            ),
        ]
    return QuestionPool(
        schema_version=1,
        excluded_count=0,
        questions=questions,
        metadata=metadata,
    )


def test_write_epub_creates_valid_epub(tmp_path: Path) -> None:
    pool = _sample_pool()
    epub_path = write_epub(
        pool.questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
    )
    assert epub_path.exists()
    assert epub_path.stat().st_size > 0
    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        assert "mimetype" in names


def test_write_epub_contains_question_content(tmp_path: Path) -> None:
    pool = _sample_pool()
    epub_path = write_epub(
        pool.questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml")]
        assert len(chapter_files) >= 1
        content = zf.read(chapter_files[0]).decode("utf-8")
        assert "E1A01" in content


def test_write_epub_with_metadata(tmp_path: Path) -> None:
    metadata = PoolMetadata(
        subelement_titles={"E1": "Commission's Rules"},
        group_titles={"E1A": "Operating Standards"},
        subelement_friendly_titles={"E1": "Rules & Regs"},
        group_friendly_titles={"E1A": "Standards"},
    )
    pool = _sample_pool(metadata=metadata)
    epub_path = write_epub(
        pool.questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
        metadata=metadata,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml")]
        content = zf.read(chapter_files[0]).decode("utf-8")
        assert "Rules &amp; Regs" in content


def test_write_epub_embeds_base64_images(tmp_path: Path) -> None:
    questions = [
        PoolQuestion(
            question_id="E5C11",
            question_text="What is shown in this figure?",
            choices=["Answer A", "Answer B", "Answer C", "Answer D"],
            correct_choice_index=0,
            group="E5C",
            subelement="E5",
            images=[
                QuestionImage(
                    media_type="image/png",
                    data_base64=PNG_1X1_BASE64,
                )
            ],
        ),
    ]
    epub_path = write_epub(
        questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        image_files = [n for n in zf.namelist() if "images/" in n]
        assert len(image_files) >= 1


def test_write_epub_embeds_file_images(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "image1.png").write_bytes(base64.b64decode(PNG_1X1_BASE64, validate=True))

    questions = [
        PoolQuestion(
            question_id="E5C11",
            question_text="What is shown in this figure?",
            choices=["Answer A", "Answer B", "Answer C", "Answer D"],
            correct_choice_index=0,
            group="E5C",
            subelement="E5",
            image_paths=["assets/image1.png"],
            images=[QuestionImage(path="assets/image1.png")],
        ),
    ]
    epub_path = write_epub(
        questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
        image_root_dir=tmp_path,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        image_files = [n for n in zf.namelist() if "images/" in n]
        assert len(image_files) >= 1


def test_write_epub_multiple_subelements(tmp_path: Path) -> None:
    questions = [
        PoolQuestion(
            question_id="E1A01",
            question_text="What is one purpose?",
            choices=["Advance the art", "B", "C", "D"],
            correct_choice_index=0,
            group="E1A",
            subelement="E1",
        ),
        PoolQuestion(
            question_id="E2A01",
            question_text="What is another purpose?",
            choices=["Communication", "B", "C", "D"],
            correct_choice_index=0,
            group="E2A",
            subelement="E2",
        ),
    ]
    epub_path = write_epub(
        questions,
        tmp_path / "output.epub",
        mode="literal",
        omit_id=False,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml") and "chapter_" in n]
        assert len(chapter_files) == 2


def test_write_epub_augmented_qa_includes_about_section(tmp_path: Path) -> None:
    questions = [
        PoolQuestion(
            question_id="E1A01",
            question_text="What is one purpose?",
            choices=["Advance the art", "B", "C", "D"],
            correct_choice_index=0,
            group="E1A",
            subelement="E1",
            llm=LlmProse(
                prose_fact="Cleaner prose sentence.",
                answer_explanation="Helpful context.",
                status="accepted",
                validation=ProseValidation(True, True, True),
                source_hash="sha256:test",
            ),
        ),
    ]
    epub_path = write_epub(
        questions,
        tmp_path / "output.epub",
        mode="qa",
        omit_id=False,
    )
    with zipfile.ZipFile(epub_path, "r") as zf:
        chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml")]
        content = zf.read(chapter_files[0]).decode("utf-8")
        assert "About this edition" in content
        assert (
            "each question and answer line is verbatim from the official question pool"
            in content
        )


def test_build_from_pool_json_produces_epub(tmp_path: Path) -> None:
    pool_json = tmp_path / "pool.json"
    write_question_pool(_sample_pool(), pool_json)

    summary = build_from_pool_json(pool_json, out_dir=tmp_path, mode="literal", omit_id=False)

    assert summary.epub_path is not None
    assert summary.epub_path.exists()
    assert summary.epub_path.stat().st_size > 0


def test_question_html_lines_split_qa_content() -> None:
    lines = _question_html_lines(
        "E1A01: Q: What is one purpose of the Amateur Radio Service? A: Advance the art."
    )

    assert lines == [
        '<p class="question-id">E1A01</p>',
        '<p class="qa-line qa-question"><span class="qa-label">Q:</span> '
        "What is one purpose of the Amateur Radio Service?</p>",
        '<p class="qa-line qa-answer"><span class="qa-label">A:</span> Advance the art.</p>',
    ]


def test_question_html_lines_keep_non_qa_content_single_line() -> None:
    lines = _question_html_lines("E1A01: This is a literal fact sentence.")

    assert lines == ["<p><strong>E1A01:</strong> This is a literal fact sentence.</p>"]


def test_question_html_lines_include_llm_explanation_block() -> None:
    lines = _question_html_lines(
        "E1A01: Q: What is one purpose of the Amateur Radio Service? A: Advance the art.\n"
        "Notes: This adds extra context."
    )

    assert lines == [
        '<p class="question-id">E1A01</p>',
        '<p class="qa-line qa-question"><span class="qa-label">Q:</span> '
        "What is one purpose of the Amateur Radio Service?</p>",
        '<p class="qa-line qa-answer"><span class="qa-label">A:</span> Advance the art.</p>',
        '<p class="llm-explanation"><span class="llm-label">'
        "Notes: </span>This adds extra context.</p>",
    ]
