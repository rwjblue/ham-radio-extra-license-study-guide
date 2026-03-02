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
    assert "Next section, E1A: Band Privileges." in content
    assert "Next section, E1B: Station Limits." in content
    assert "Section recap: review these rules and examples before moving on." in content
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


def test_write_audio_script_splits_overlong_facts(tmp_path: Path) -> None:
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

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    long_lines = [line for line in lines if len(line) > 160]
    assert long_lines == []


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
