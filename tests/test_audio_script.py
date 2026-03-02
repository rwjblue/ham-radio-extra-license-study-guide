from __future__ import annotations

import json
from pathlib import Path

from extra_facts.models import PoolMetadata, PoolQuestion
from extra_facts.render import write_audio_script


def _question(question_id: str, text: str, answer: str) -> PoolQuestion:
    return PoolQuestion(
        question_id=question_id,
        question_text=text,
        choices=[answer, "x", "y", "z"],
        correct_choice_index=0,
        group=question_id[:3],
        subelement=question_id[:2],
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
        "totally within the band: 3 kilohertz above the lower band edge.\n\n"
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
    assert "Section E1A.\n\nThe maximum symbol rate is 1200 baud.\n\n" in content
    assert (
        "The maximum symbol rate is 1200 baud.\n\n"
        "Which of the following is true: Option A.\n\n"
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
