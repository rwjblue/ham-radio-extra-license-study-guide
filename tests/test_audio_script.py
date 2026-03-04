from __future__ import annotations

import json
from pathlib import Path

from extra_facts.models import PoolMetadata, PoolQuestion
from extra_facts.render import write_audio_script


def _question(
    question_id: str,
    text: str,
    answer: str,
    image_paths: list[str] | None = None,
) -> PoolQuestion:
    return PoolQuestion(
        question_id=question_id,
        question_text=text,
        choices=[answer, "x", "y", "z"],
        correct_choice_index=0,
        group=question_id[:3],
        subelement=question_id[:2],
        image_paths=image_paths or [],
    )


def test_write_audio_script_adds_spoken_headers_and_omits_ids(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is the maximum symbol rate?", "1200 baud"),
        _question("E1A02", "Which of the following is true?", "Option A"),
        _question("E1B01", "How many operators may transmit?", "Three"),
    ]
    metadata = PoolMetadata(
        subelement_titles={"E1": "COMMISSION'S RULES"},
        group_titles={"E1A": "Frequency privileges", "E1B": "Station restrictions"},
        subelement_friendly_titles={"E1": "Operating Rules"},
        group_friendly_titles={"E1A": "Band Privileges", "E1B": "Station Limits"},
    )

    path, chapters_dir, manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="tts",
        omit_id=True,
        metadata=metadata,
    )

    content = path.read_text(encoding="utf-8")
    assert "Chapter E1: Operating Rules." in content
    assert "Chapter E1: Operating Rules.\n[[SHORT_PAUSE]]\n\n" in content
    assert "Section E1A." in content
    assert "Section E1B." in content
    assert "Focus on the core ideas and practical limits in this chapter." not in content
    assert "Section recap: review these rules and examples before moving on." not in content
    assert "E1A01:" not in content
    assert (chapters_dir / "chapter-01.txt").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["chapter_count"] == 1
    assert manifest["chapters"][0]["code"] == "E1"


def test_write_audio_script_can_include_ids(tmp_path: Path) -> None:
    questions = [_question("E1A01", "What is the maximum symbol rate?", "1200 baud")]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=False,
    )

    content = path.read_text(encoding="utf-8")
    assert "E1A01: The maximum symbol rate is 1200 baud." in content


def test_write_audio_script_expands_khz_and_mhz_for_audio(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is the bandwidth?", "3 kHz"),
        _question("E1A02", "What is the carrier frequency?", "14.2 MHz"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="prose",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "3 kilohertz" in content
    assert "14.2 megahertz" in content
    assert "kHz" not in content
    assert "MHz" not in content


def test_write_audio_script_expands_ghz_for_audio(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is the uplink frequency?", "5.8 GHz"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="prose",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "5.8 gigahertz" in content
    assert "GHz" not in content


def test_write_audio_script_expands_usb_lsb_ssb_for_audio(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What modulation is used?", "USB"),
        _question("E1A02", "What alternative is common?", "LSB"),
        _question("E1A03", "What family includes both?", "SSB"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="prose",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "upper side band" in content
    assert "lower side band" in content
    assert "single side band" in content
    assert " USB" not in content
    assert " LSB" not in content
    assert " SSB" not in content




def test_write_audio_script_adjusts_articles_for_usb_and_ssb(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "Which mode is selected?", "a USB signal"),
        _question("E1A02", "What type of emission is generated?", "an SSB emission"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="prose",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "an upper side band signal" in content
    assert "a single side band emission" in content
    assert "a upper side band" not in content
    assert "an single side band" not in content


def test_write_audio_script_adjusts_capitalized_articles_for_usb_and_ssb(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "Which mode is selected?", "A USB signal"),
        _question("E1A02", "What type of emission is generated?", "An SSB emission"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="prose",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "An upper side band signal" in content
    assert "A single side band emission" in content
    assert "An single side band" not in content

def test_write_audio_script_does_not_force_newline_within_fact_paragraph(tmp_path: Path) -> None:
    questions = [
        _question(
            "E1A01",
            (
                "When using a transceiver that displays the carrier frequency of phone "
                "signals, what is the lowest frequency at which a properly adjusted LSB "
                "emission will be totally within the band?"
            ),
            "3 kHz above the lower band edge",
        )
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert (
        "When using a transceiver that displays the carrier frequency of phone signals.\n"
        "The lowest frequency"
    ) not in content
    assert (
        "\n\nWhen using a transceiver that displays the carrier frequency of phone signals, "
        "what is the lowest frequency at which a properly adjusted lower side "
        "band emission will be "
        "totally within the band: 3 kilohertz above the lower band edge.\n"
        "[[SHORT_PAUSE]]\n\n"
    ) in content


def test_write_audio_script_uses_blank_lines_between_sections_and_facts(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is the maximum symbol rate?", "1200 baud"),
        _question("E1A02", "Which of the following is true?", "Option A"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "Chapter E1.\n[[SHORT_PAUSE]]\n\nSection E1A.\n\n" in content
    assert "Section E1A.\n\nThe maximum symbol rate is 1200 baud.\n[[SHORT_PAUSE]]\n\n" in content
    assert (
        "The maximum symbol rate is 1200 baud.\n[[SHORT_PAUSE]]\n\n"
        "Which of the following is true: Option A.\n[[SHORT_PAUSE]]\n\n"
    ) in content


def test_write_audio_script_emits_chapter_files_in_order(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is true?", "A"),
        _question("E2A01", "What is also true?", "B"),
    ]
    metadata = PoolMetadata(
        subelement_titles={"E1": "Rules", "E2": "Procedures"},
        group_titles={"E1A": "First Group", "E2A": "Second Group"},
    )

    _path, chapters_dir, manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=True,
        metadata=metadata,
    )

    assert (chapters_dir / "chapter-01.txt").exists()
    assert (chapters_dir / "chapter-02.txt").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["chapter_count"] == 2
    assert [chapter["code"] for chapter in manifest["chapters"]] == ["E1", "E2"]


def test_write_audio_script_normalizes_all_caps_chapter_titles(tmp_path: Path) -> None:
    questions = [_question("E1A01", "What is true?", "A")]
    metadata = PoolMetadata(
        subelement_titles={"E1": "COMMISSION RULES"},
        group_titles={"E1A": "BAND PRIVILEGES"},
    )

    path, _chapters_dir, manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=True,
        metadata=metadata,
    )

    content = path.read_text(encoding="utf-8")
    assert "Chapter E1: Commission Rules." in content

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["chapters"][0]["title"] == "Commission Rules"


def test_write_audio_script_removes_figure_questions_and_reports_count(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is true?", "A", image_paths=["media/image1.png"]),
        _question("E1A02", "What is also true?", "B"),
        _question("E1A03", "What is another true thing?", "C", image_paths=["media/image2.png"]),
        _question("E1B01", "How many operators may transmit?", "Three"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="literal",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert (
        "Section E1A. 2 questions that require figures were removed from this section."
        in content
    )
    assert "Section E1B." in content
    assert "True is A." not in content
    assert "Another true thing is C." not in content
    assert "Also true is B." in content


def test_write_audio_script_qa_mode_includes_question_and_answer(tmp_path: Path) -> None:
    questions = [_question("E1A01", "What is the maximum symbol rate?", "1200 baud")]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="qa",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert "What is the maximum symbol rate?\n[[SHORT_PAUSE]]\n1200 baud." in content
    assert "Q:" not in content
    assert "A:" not in content




def test_write_audio_script_qa_mode_expands_all_choices_correct_answer(tmp_path: Path) -> None:
    questions = [
        PoolQuestion(
            question_id="E1A01",
            question_text="Which statements are true?",
            choices=[
                "Statement one is true",
                "Statement two is true",
                "Statement three is true",
                "All these choices are correct",
            ],
            correct_choice_index=3,
            group="E1A",
            subelement="E1",
        )
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="qa",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert (
        "Which statements are true?\n"
        "[[SHORT_PAUSE]]\n"
        "All these choices are correct:\n"
        "[[SHORT_PAUSE]]\n"
        "Statement one is true\n"
        "[[SHORT_PAUSE]]\n"
        "Statement two is true\n"
        "[[SHORT_PAUSE]]\n"
        "Statement three is true\n"
        "[[SHORT_PAUSE]]"
    ) in content
    assert "\n- Statement one is true" not in content


def test_write_audio_script_inserts_pause_marker_between_questions(tmp_path: Path) -> None:
    questions = [
        _question("E1A01", "What is true?", "A"),
        _question("E1A02", "What is also true?", "B"),
    ]

    path, _chapters_dir, _manifest_path = write_audio_script(
        questions,
        out_dir=tmp_path,
        mode="qa",
        omit_id=True,
    )

    content = path.read_text(encoding="utf-8")
    assert (
        "What is true?\n[[SHORT_PAUSE]]\nA.\n[[SHORT_PAUSE]]\n\n"
        "What is also true?\n[[SHORT_PAUSE]]\nB."
    ) in content

def test_build_audio_script_from_pool_json_qa_mode_uses_qa_filename(tmp_path: Path) -> None:
    from extra_facts.build import build_audio_script_from_pool_json
    from extra_facts.intermediate import write_question_pool
    from extra_facts.models import QuestionPool

    pool_json = tmp_path / "pool.json"
    write_question_pool(
        QuestionPool(
            schema_version=1,
            excluded_count=0,
            questions=[_question("E1A01", "What is the maximum symbol rate?", "1200 baud")],
        ),
        pool_json,
    )

    summary = build_audio_script_from_pool_json(
        pool_json_path=pool_json,
        out_dir=tmp_path / "audio",
        mode="qa",
        omit_id=True,
    )

    assert summary.script_path.name == "script.txt"
