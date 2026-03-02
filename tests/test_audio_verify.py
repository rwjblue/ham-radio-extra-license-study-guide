from __future__ import annotations

import json
from pathlib import Path

import pytest

from extra_facts.audio_verify import AudioVerificationError, verify_audio_from_manifest


def _write_manifest(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    chapters_dir = audio_dir / "chapters"
    chapters_dir.mkdir(parents=True)
    (chapters_dir / "chapter-01.mp3").write_bytes(b"a")
    (chapters_dir / "chapter-02.mp3").write_bytes(b"b")
    (audio_dir / "extra_facts_audio.mp3").write_bytes(b"merged")

    manifest = {
        "schema_version": 1,
        "chapter_count": 2,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "audio_path": str((chapters_dir / "chapter-01.mp3").resolve()),
                "duration_seconds": 10.0,
                "start_seconds": 0.0,
            },
            {
                "number": 2,
                "code": "E2",
                "title": "Two",
                "audio_path": str((chapters_dir / "chapter-02.mp3").resolve()),
                "duration_seconds": 12.5,
                "start_seconds": 10.0,
            },
        ],
        "audio_render": {
            "merged_audio_path": str((audio_dir / "extra_facts_audio.mp3").resolve()),
            "total_duration_seconds": 22.5,
        },
    }
    path = audio_dir / "audio_chapters_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def test_verify_audio_from_manifest_passes(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    summary = verify_audio_from_manifest(
        manifest_path=manifest_path,
        duration_probe=lambda path: 10.0 if path.name == "chapter-01.mp3" else 12.5,
        chapter_count_probe=lambda _path: 2,
    )
    assert summary.chapter_count == 2
    assert summary.chapter_markers_verified is True
    assert summary.total_duration_seconds == 22.5


def test_verify_audio_from_manifest_fails_when_marker_count_too_low(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    with pytest.raises(AudioVerificationError, match="chapter marker count"):
        verify_audio_from_manifest(
            manifest_path=manifest_path,
            duration_probe=lambda path: 10.0 if path.name == "chapter-01.mp3" else 12.5,
            chapter_count_probe=lambda _path: 1,
        )


def test_verify_audio_from_manifest_fails_when_timing_incorrect(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["chapters"][1]["start_seconds"] = 9.0
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(AudioVerificationError, match="does not match expected"):
        verify_audio_from_manifest(
            manifest_path=manifest_path,
            duration_probe=lambda path: 10.0 if path.name == "chapter-01.mp3" else 12.5,
            chapter_count_probe=lambda _path: 2,
        )


def test_verify_audio_from_manifest_allows_missing_merged_when_requested(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["audio_render"]["merged_audio_path"] = None
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = verify_audio_from_manifest(
        manifest_path=manifest_path,
        require_merged_audio=False,
        require_chapter_markers=False,
        duration_probe=lambda path: 10.0 if path.name == "chapter-01.mp3" else 12.5,
        chapter_count_probe=lambda _path: 0,
    )
    assert summary.merged_audio_path is None
