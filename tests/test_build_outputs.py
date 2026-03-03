from __future__ import annotations

import base64
from pathlib import Path

from extra_facts.build import build_from_pool_json
from extra_facts.intermediate import write_question_pool
from extra_facts.models import PoolQuestion, QuestionImage, QuestionPool

PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W6mQAAAAASUVORK5CYII="
)


def test_build_writes_light_and_dark_pdf_outputs(tmp_path: Path) -> None:
    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
                PoolQuestion(
                    question_id="E1A01",
                    question_text="What is one purpose of the Amateur Radio Service?",
                    choices=["Advance the art", "Entertainment", "Advertising", "None"],
                    correct_choice_index=0,
                    group="E1A",
                    subelement="E1",
                )
            ],
        ),
        pool_json,
    )

    summary = build_from_pool_json(pool_json, out_dir=tmp_path, mode="literal", omit_id=False)

    assert summary.text_path.exists()
    assert summary.pdf_path.exists()
    assert summary.dark_pdf_path is not None
    assert summary.dark_pdf_path.exists()


def test_build_embeds_question_images_from_json_payload(tmp_path: Path) -> None:
    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
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
                )
            ],
        ),
        pool_json,
    )

    summary = build_from_pool_json(pool_json, out_dir=tmp_path, mode="literal", omit_id=False)

    assert summary.pdf_path.exists()
    assert summary.pdf_path.stat().st_size > 0


def test_build_resolves_image_paths_relative_to_pool_json(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "image1.png").write_bytes(base64.b64decode(PNG_1X1_BASE64, validate=True))

    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
                PoolQuestion(
                    question_id="E5C11",
                    question_text="What is shown in this figure?",
                    choices=["Answer A", "Answer B", "Answer C", "Answer D"],
                    correct_choice_index=0,
                    group="E5C",
                    subelement="E5",
                    image_paths=["assets/image1.png"],
                    images=[QuestionImage(path="assets/image1.png")],
                )
            ],
        ),
        pool_json,
    )

    out_dir = tmp_path / "static"
    summary = build_from_pool_json(pool_json, out_dir=out_dir, mode="literal", omit_id=False)

    assert summary.pdf_path.exists()
    assert summary.pdf_path.stat().st_size > 0


def test_build_qa_mode_uses_qa_file_prefix(tmp_path: Path) -> None:
    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
                PoolQuestion(
                    question_id="E1A01",
                    question_text="What is one purpose of the Amateur Radio Service?",
                    choices=["Advance the art", "Entertainment", "Advertising", "None"],
                    correct_choice_index=0,
                    group="E1A",
                    subelement="E1",
                )
            ],
        ),
        pool_json,
    )

    summary = build_from_pool_json(pool_json, out_dir=tmp_path, mode="qa", omit_id=False)

    assert summary.text_path.name == "qa.txt"
    assert summary.pdf_path.name == "qa.pdf"
    assert summary.epub_path is not None
    assert summary.epub_path.name == "qa.epub"


def test_build_prose_mode_uses_augmented_file_prefix(tmp_path: Path) -> None:
    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
                PoolQuestion(
                    question_id="E1A01",
                    question_text="What is one purpose of the Amateur Radio Service?",
                    choices=["Advance the art", "Entertainment", "Advertising", "None"],
                    correct_choice_index=0,
                    group="E1A",
                    subelement="E1",
                )
            ],
        ),
        pool_json,
    )

    summary = build_from_pool_json(pool_json, out_dir=tmp_path, mode="prose", omit_id=False)

    assert summary.text_path.name == "facts.txt"
    assert summary.pdf_path.name == "facts.pdf"
    assert summary.dark_pdf_path is not None
    assert summary.dark_pdf_path.name == "facts-dark.pdf"
    assert summary.epub_path is not None
    assert summary.epub_path.name == "facts.epub"
