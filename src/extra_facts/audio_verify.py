from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from .audio import probe_mp3_duration
from .models import AudioVerifySummary

TIMING_TOLERANCE_SECONDS = 0.05
DURATION_TOLERANCE_SECONDS = 0.25
TOTAL_DURATION_TOLERANCE_SECONDS = 0.2

DurationProbe = Callable[[Path], float]
ChapterCountProbe = Callable[[Path], int]


class AudioVerificationError(RuntimeError):
    pass


def verify_audio_from_manifest(
    manifest_path: Path,
    require_merged_audio: bool = True,
    require_chapter_markers: bool = True,
    duration_probe: DurationProbe | None = None,
    chapter_count_probe: ChapterCountProbe | None = None,
) -> AudioVerifySummary:
    payload = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    chapters_payload = payload.get("chapters")
    if not isinstance(chapters_payload, list):
        raise AudioVerificationError("Manifest is missing 'chapters' list")
    chapters = cast(list[dict[str, Any]], chapters_payload)

    expected_count = int(payload.get("chapter_count", len(chapters)))
    if expected_count != len(chapters):
        raise AudioVerificationError(
            f"Manifest chapter_count={expected_count} does not match chapters={len(chapters)}"
        )

    _verify_chapter_sequence(chapters)
    duration_fn = duration_probe or probe_mp3_duration
    chapter_probe = chapter_count_probe or probe_mp3_chapter_count

    total_manifest_duration = 0.0
    expected_start = 0.0
    previous_start = -1.0

    for chapter in chapters:
        chapter_number = int(chapter["number"])
        audio_path = _resolve_audio_path(
            chapter,
            manifest_path=manifest_path,
            chapter_number=chapter_number,
        )
        recorded_duration = _required_float(chapter, "duration_seconds", chapter_number)
        recorded_start = _required_float(chapter, "start_seconds", chapter_number)

        if recorded_duration <= 0:
            raise AudioVerificationError(
                f"Chapter {chapter_number} has non-positive duration: {recorded_duration}"
            )
        if recorded_start < 0:
            raise AudioVerificationError(
                f"Chapter {chapter_number} has negative start_seconds: {recorded_start}"
            )
        if recorded_start + 1e-9 < previous_start:
            raise AudioVerificationError(
                f"Chapter {chapter_number} start_seconds is not monotonic: {recorded_start}"
            )
        if abs(recorded_start - expected_start) > TIMING_TOLERANCE_SECONDS:
            raise AudioVerificationError(
                f"Chapter {chapter_number} start_seconds {recorded_start} "
                f"does not match expected {expected_start:.3f}"
            )

        measured_duration = duration_fn(audio_path)
        if abs(measured_duration - recorded_duration) > DURATION_TOLERANCE_SECONDS:
            raise AudioVerificationError(
                f"Chapter {chapter_number} duration mismatch: "
                f"recorded={recorded_duration} measured={measured_duration:.3f}"
            )

        total_manifest_duration += recorded_duration
        expected_start += recorded_duration
        previous_start = recorded_start

    merged_audio_path = _resolve_merged_audio_path(payload, manifest_path=manifest_path)
    chapter_markers_verified = False
    if merged_audio_path is None:
        if require_merged_audio:
            raise AudioVerificationError("Merged audio is required but missing from manifest")
    else:
        if not merged_audio_path.exists():
            raise AudioVerificationError(f"Merged audio file does not exist: {merged_audio_path}")
        if require_chapter_markers:
            marker_count = chapter_probe(merged_audio_path)
            if marker_count < len(chapters):
                raise AudioVerificationError(
                    f"Merged audio chapter marker count {marker_count} is less than {len(chapters)}"
                )
            chapter_markers_verified = True

    audio_render = payload.get("audio_render")
    if isinstance(audio_render, dict):
        audio_render_dict = cast(dict[str, object], audio_render)
        recorded_total = audio_render_dict.get("total_duration_seconds")
        if isinstance(recorded_total, int | float) and (
            abs(float(recorded_total) - total_manifest_duration) > TOTAL_DURATION_TOLERANCE_SECONDS
        ):
            raise AudioVerificationError(
                "Manifest total_duration_seconds does not match chapter duration sum: "
                f"{recorded_total} vs {total_manifest_duration:.3f}"
            )

    return AudioVerifySummary(
        manifest_path=manifest_path,
        chapter_count=len(chapters),
        chapter_markers_verified=chapter_markers_verified,
        merged_audio_path=merged_audio_path,
        total_duration_seconds=round(total_manifest_duration, 3),
    )


def probe_mp3_chapter_count(path: Path) -> int:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_chapters",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = cast(dict[str, Any], json.loads(result.stdout or "{}"))
    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return 0
    chapter_list = cast(list[object], chapters)
    return len(chapter_list)


def _verify_chapter_sequence(chapters: list[dict[str, Any]]) -> None:
    expected = 1
    for chapter in chapters:
        raw_number = chapter.get("number")
        if not isinstance(raw_number, int):
            raise AudioVerificationError(f"Chapter number must be int, got: {raw_number!r}")
        if raw_number != expected:
            raise AudioVerificationError(
                f"Chapter sequence is not contiguous at {raw_number}; expected {expected}"
            )
        expected += 1


def _required_float(chapter: dict[str, Any], key: str, chapter_number: int) -> float:
    value = chapter.get(key)
    if not isinstance(value, int | float):
        raise AudioVerificationError(f"Chapter {chapter_number} is missing numeric {key}")
    return float(value)


def _resolve_audio_path(chapter: dict[str, Any], manifest_path: Path, chapter_number: int) -> Path:
    value = chapter.get("audio_path")
    if not isinstance(value, str) or not value:
        raise AudioVerificationError(f"Chapter {chapter_number} missing audio_path")
    path = _resolve_manifest_path(value, manifest_path=manifest_path)
    if not path.exists():
        raise AudioVerificationError(f"Chapter {chapter_number} audio file is missing: {path}")
    return path


def _resolve_merged_audio_path(payload: dict[str, Any], manifest_path: Path) -> Path | None:
    audio_render = payload.get("audio_render")
    if not isinstance(audio_render, dict):
        return None
    audio_render_dict = cast(dict[str, object], audio_render)
    value = audio_render_dict.get("merged_audio_path")
    if not isinstance(value, str) or not value:
        return None
    return _resolve_manifest_path(value, manifest_path=manifest_path)


def _resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (manifest_path.parent / path).resolve()
