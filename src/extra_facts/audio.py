from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import requests


class TtsClient(Protocol):
    def synthesize(self, text: str) -> bytes:
        ...


DurationProbe = Callable[[Path], float]
AudioMerger = Callable[[list[Path], Path], None]
TTS_MAX_CHARS = 3500


class OpenAITtsClient:
    def __init__(
        self,
        model: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {api_key_env}")
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.speed = speed

    def synthesize(self, text: str) -> bytes:
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "voice": self.voice,
                "input": text,
                "response_format": self.response_format,
                "speed": self.speed,
            },
            timeout=180,
        )
        if response.status_code >= 400:
            body = response.text.strip()
            raise RuntimeError(f"OpenAI TTS request failed ({response.status_code}): {body}")
        return response.content


@dataclass(frozen=True)
class AudioRenderResult:
    chapter_count: int
    manifest_in_path: Path
    manifest_out_path: Path
    chapters_audio_dir: Path
    merged_audio_path: Path | None
    total_duration_seconds: float


def render_audio_from_manifest(
    manifest_path: Path,
    out_dir: Path,
    client: TtsClient,
    output_format: str = "mp3",
    merge_output: bool = True,
    out_manifest_path: Path | None = None,
    probe_duration: DurationProbe | None = None,
    merge_audio: AudioMerger | None = None,
) -> AudioRenderResult:
    payload = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    chapters_payload = payload.get("chapters")
    if not isinstance(chapters_payload, list):
        raise RuntimeError("Manifest is missing 'chapters' list")
    chapters = cast(list[dict[str, Any]], chapters_payload)

    out_dir.mkdir(parents=True, exist_ok=True)
    chapters_audio_dir = out_dir / "chapters"
    chapters_audio_dir.mkdir(parents=True, exist_ok=True)

    probe_fn = probe_duration or probe_mp3_duration
    merge_fn = merge_audio or merge_mp3_files

    start_seconds = 0.0
    rendered_paths: list[Path] = []
    for chapter in chapters:
        chapter_number = int(chapter["number"])
        text_path_value = chapter.get("text_path")
        if not isinstance(text_path_value, str):
            raise RuntimeError(f"Chapter {chapter_number} missing text_path")
        text_path = _resolve_path(text_path_value, manifest_path=manifest_path)
        text = text_path.read_text(encoding="utf-8").strip()
        if not text:
            raise RuntimeError(f"Chapter text is empty: {text_path}")

        audio_file_name = f"chapter-{chapter_number:02d}.{output_format}"
        audio_path = chapters_audio_dir / audio_file_name
        segment_paths = _render_tts_segments(
            text=text,
            chapter_number=chapter_number,
            output_format=output_format,
            chapters_audio_dir=chapters_audio_dir,
            client=client,
        )
        if len(segment_paths) == 1:
            audio_path.write_bytes(segment_paths[0].read_bytes())
        else:
            merge_fn(segment_paths, audio_path)
        _cleanup_temp_segments(segment_paths)

        duration_seconds = probe_fn(audio_path)
        chapter["audio_path"] = str(audio_path.as_posix())
        chapter["duration_seconds"] = round(duration_seconds, 3)
        chapter["start_seconds"] = round(start_seconds, 3)
        start_seconds += duration_seconds
        rendered_paths.append(audio_path)

    merged_audio_path: Path | None = None
    if merge_output and rendered_paths:
        merged_audio_path = out_dir / f"extra_facts_audio.{output_format}"
        merge_fn(rendered_paths, merged_audio_path)

    payload["audio_render"] = {
        "provider": "openai",
        "output_format": output_format,
        "merged_audio_path": (
            str(merged_audio_path.as_posix()) if merged_audio_path is not None else None
        ),
        "total_duration_seconds": round(start_seconds, 3),
        "rendered_at": datetime.now(UTC).isoformat(),
    }

    target_manifest = out_manifest_path or manifest_path
    target_manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return AudioRenderResult(
        chapter_count=len(chapters),
        manifest_in_path=manifest_path,
        manifest_out_path=target_manifest,
        chapters_audio_dir=chapters_audio_dir,
        merged_audio_path=merged_audio_path,
        total_duration_seconds=round(start_seconds, 3),
    )


def probe_mp3_duration(path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    raw = result.stdout.strip()
    return float(raw)


def merge_mp3_files(inputs: list[Path], output_path: Path) -> None:
    if not inputs:
        raise RuntimeError("No chapter audio files to merge")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as list_file:
        list_path = Path(list_file.name)
        for path in inputs:
            list_file.write(f"file '{path.resolve().as_posix()}'\n")

    try:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
    finally:
        list_path.unlink(missing_ok=True)


def _resolve_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return (manifest_path.parent / path).resolve()


def _render_tts_segments(
    text: str,
    chapter_number: int,
    output_format: str,
    chapters_audio_dir: Path,
    client: TtsClient,
) -> list[Path]:
    chunks = _split_text_for_tts(text, max_chars=TTS_MAX_CHARS)
    segment_paths: list[Path] = []
    for segment_index, chunk in enumerate(chunks, start=1):
        segment_name = (
            f"chapter-{chapter_number:02d}.segment-{segment_index:03d}.{output_format}"
        )
        segment_path = chapters_audio_dir / segment_name
        segment_path.write_bytes(client.synthesize(chunk))
        segment_paths.append(segment_path)
    return segment_paths


def _split_text_for_tts(text: str, max_chars: int) -> list[str]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        wrapped_segments = textwrap.wrap(
            paragraph,
            width=max_chars,
            break_long_words=False,
            break_on_hyphens=False,
        )
        parts = wrapped_segments if wrapped_segments else [paragraph]
        for part in parts:
            part_len = len(part)
            sep = 1 if current else 0
            if current and current_len + sep + part_len > max_chars:
                chunks.append("\n".join(current))
                current = [part]
                current_len = part_len
                continue
            if current:
                current_len += sep + part_len
            else:
                current_len = part_len
            current.append(part)

    if current:
        chunks.append("\n".join(current))
    return chunks


def _cleanup_temp_segments(segment_paths: list[Path]) -> None:
    for segment_path in segment_paths:
        segment_path.unlink(missing_ok=True)
