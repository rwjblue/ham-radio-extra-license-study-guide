from __future__ import annotations

from pathlib import Path

from extra_facts.build import build_from_pool_json
from extra_facts.intermediate import write_question_pool
from extra_facts.models import PoolQuestion, QuestionPool


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
