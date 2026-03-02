from __future__ import annotations

from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from extra_facts import build as build_module
from extra_facts.intermediate import read_question_pool, write_question_pool
from extra_facts.models import PoolQuestion, QuestionImage, QuestionPool
from extra_facts.prose import ProseRunSummary

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc"
    b"\xff\x1f\x00\x03\x03\x02\x00\xeeV\xead\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeOpenAIProseClient:
    def __init__(self, model: str, prompt_version: str) -> None:
        _ = (model, prompt_version)


def test_generate_prose_copies_referenced_assets_next_to_output_json(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_dir = tmp_path / "source"
    source_assets = source_dir / "assets"
    source_assets.mkdir(parents=True)
    (source_assets / "e5c10-01.png").write_bytes(PNG_1X1)

    input_json = source_dir / "extra_pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[
                PoolQuestion(
                    question_id="E5C10",
                    question_text="Which impedance does this chart show?",
                    choices=["50 ohms", "75 ohms", "100 ohms", "25 ohms"],
                    correct_choice_index=0,
                    group="E5C",
                    subelement="E5",
                    image_paths=["assets/e5c10-01.png"],
                    images=[QuestionImage(path="assets/e5c10-01.png")],
                )
            ],
        ),
        input_json,
    )

    output_json = tmp_path / "prose" / "extra_pool_prose.json"

    monkeypatch.setattr(build_module, "OpenAIProseClient", _FakeOpenAIProseClient)

    def _fake_enrich_pool_with_prose(
        pool: QuestionPool,
        **kwargs: object,
    ) -> tuple[QuestionPool, ProseRunSummary]:
        _ = kwargs
        return (
            pool,
            ProseRunSummary(total=1, target=1, generated=1, accepted=1, fallback=0, errors=0),
        )

    monkeypatch.setattr(build_module, "enrich_pool_with_prose", _fake_enrich_pool_with_prose)

    def _fake_enrich_pool_metadata_with_headings(
        pool: QuestionPool,
        client: object,
    ) -> QuestionPool:
        _ = client
        return pool

    monkeypatch.setattr(
        build_module,
        "enrich_pool_metadata_with_headings",
        _fake_enrich_pool_metadata_with_headings,
    )

    build_module.generate_prose_for_pool(
        pool_json_path=input_json,
        out_json_path=output_json,
        model="fake-model",
        prompt_version="v1",
        max_questions=None,
        resume=False,
        workers=1,
        max_attempts=1,
    )

    copied_asset = output_json.parent / "assets" / "e5c10-01.png"
    assert output_json.exists()
    assert copied_asset.exists()
    assert copied_asset.read_bytes() == PNG_1X1

    output_pool = read_question_pool(output_json)
    assert output_pool.questions[0].image_paths == ["assets/e5c10-01.png"]
