from __future__ import annotations

import hashlib
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
from requests.adapters import HTTPAdapter
from requests_cache import CachedSession


class TtsClient(Protocol):
    def synthesize(self, text: str) -> bytes:
        ...


DurationProbe = Callable[[Path], float]
AudioMerger = Callable[[list[Path], Path], None]
ChapterMarkerEmbedder = Callable[[list[dict[str, Any]], Path], None]
TTS_MAX_CHARS = 3500
DEFAULT_OPENAI_HTTP_CACHE_DIR = Path(".cache/openai-http")
DEFAULT_OPENAI_HTTP_CACHE_NAME = "audio-speech-v2"
DEFAULT_ELEVENLABS_HTTP_CACHE_DIR = Path(".cache/elevenlabs-http")
DEFAULT_ELEVENLABS_HTTP_CACHE_NAME = "text-to-speech-v1"
DEFAULT_ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_TTS_INSTRUCTIONS = (
    "High-energy study coach. Upbeat and motivating. Dynamic intonation with "
    "emphasis on key facts and numbers. Keep it natural, not theatrical."
)


class OpenAITtsClient:
    def __init__(
        self,
        model: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
        instructions: str | None = DEFAULT_TTS_INSTRUCTIONS,
        api_key_env: str = "OPENAI_API_KEY",
        cache_dir: Path | None = None,
        cache_enabled: bool | None = None,
    ) -> None:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {api_key_env}")
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.speed = speed
        self.instructions = instructions.strip() if instructions else None
        self.cache_enabled = _resolve_openai_http_cache_enabled(cache_enabled)
        self.cache_dir = _resolve_openai_http_cache_dir(cache_dir)
        self._session = _build_openai_session(self.cache_dir, self.cache_enabled)
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self._session.mount("https://", adapter)

    def synthesize(self, text: str) -> bytes:
        payload: dict[str, Any] = {
            "model": self.model,
            "voice": self.voice,
            "input": text,
            "response_format": self.response_format,
            "speed": self.speed,
        }
        if self.instructions:
            payload["instructions"] = self.instructions

        speech_response = self._post_audio_speech(self._session, payload)
        first_from_cache = bool(getattr(speech_response, "from_cache", False))
        if speech_response.status_code >= 400:
            # Retry once without cache so stale/poisoned cache entries cannot block renders.
            with requests.Session() as uncached_session:
                uncached_session.trust_env = False
                retry_response = self._post_audio_speech(uncached_session, payload)
            if retry_response.status_code < 400:
                speech_response = retry_response
            else:
                first_body = speech_response.text.strip()
                retry_body = retry_response.text.strip()
                raise RuntimeError(
                    "OpenAI TTS request failed for /v1/audio/speech; "
                    "first attempt "
                    f"({speech_response.status_code}, from_cache={first_from_cache}): "
                    f"{first_body}; retry ({retry_response.status_code}): {retry_body}"
                )

        if speech_response.status_code < 400:
            content_type = speech_response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                body = speech_response.text.strip()
                raise RuntimeError(
                    "OpenAI TTS request returned JSON for /v1/audio/speech; "
                    f"expected audio bytes. Body: {body}"
                )
            return speech_response.content

        speech_body = speech_response.text.strip()
        raise RuntimeError(
            "OpenAI TTS request failed for /v1/audio/speech "
            f"({speech_response.status_code}): {speech_body}"
        )

    def _post_audio_speech(
        self,
        session: requests.Session,
        payload: dict[str, Any],
    ) -> requests.Response:
        return session.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )


class ElevenLabsTtsClient:
    def __init__(
        self,
        model: str,
        voice_id: str,
        response_format: str = DEFAULT_ELEVENLABS_OUTPUT_FORMAT,
        language_code: str = "en",
        speed: float = 1.0,
        api_key_env: str = "ELEVENLABS_API_KEY",
        cache_dir: Path | None = None,
        cache_enabled: bool | None = None,
    ) -> None:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {api_key_env}")
        if speed != 1.0:
            raise RuntimeError(
                "ElevenLabs client currently supports speed=1.0 only for deterministic output"
            )
        self.api_key = api_key
        self.model = model
        self.voice_id = voice_id
        self.response_format = response_format
        self.language_code = language_code.strip() or "en"
        self.speed = speed
        self.cache_enabled = _resolve_elevenlabs_http_cache_enabled(cache_enabled)
        self.cache_dir = _resolve_elevenlabs_http_cache_dir(cache_dir)
        self._session = _build_elevenlabs_session(self.cache_dir, self.cache_enabled)
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self._session.mount("https://", adapter)

    def synthesize(self, text: str) -> bytes:
        payload: dict[str, Any] = {
            "text": text,
            "model_id": self.model,
            "language_code": self.language_code,
        }

        speech_response = self._post_audio_speech(self._session, payload)
        first_from_cache = bool(getattr(speech_response, "from_cache", False))
        if speech_response.status_code >= 400:
            # Retry once without cache so stale/poisoned cache entries cannot block renders.
            with requests.Session() as uncached_session:
                uncached_session.trust_env = False
                retry_response = self._post_audio_speech(uncached_session, payload)
            if retry_response.status_code < 400:
                speech_response = retry_response
            else:
                first_body = speech_response.text.strip()
                retry_body = retry_response.text.strip()
                raise RuntimeError(
                    "ElevenLabs TTS request failed for /v1/text-to-speech/{voice_id}; "
                    "first attempt "
                    f"({speech_response.status_code}, from_cache={first_from_cache}): "
                    f"{first_body}; retry ({retry_response.status_code}): {retry_body}"
                )

        if speech_response.status_code < 400:
            content_type = speech_response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                body = speech_response.text.strip()
                raise RuntimeError(
                    "ElevenLabs TTS request returned JSON for /v1/text-to-speech/{voice_id}; "
                    f"expected audio bytes. Body: {body}"
                )
            return speech_response.content

        speech_body = speech_response.text.strip()
        raise RuntimeError(
            "ElevenLabs TTS request failed for /v1/text-to-speech/{voice_id} "
            f"({speech_response.status_code}): {speech_body}"
        )

    def _post_audio_speech(
        self,
        session: requests.Session,
        payload: dict[str, Any],
    ) -> requests.Response:
        return session.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            params={"output_format": self.response_format},
            json=payload,
            timeout=180,
        )


def _resolve_openai_http_cache_enabled(config: bool | None) -> bool:
    if config is not None:
        return config
    value = os.getenv("OPENAI_HTTP_CACHE", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _resolve_openai_http_cache_dir(config: Path | None) -> Path:
    if config is not None:
        return config
    value = os.getenv("OPENAI_HTTP_CACHE_DIR", "").strip()
    if value:
        return Path(value)
    return DEFAULT_OPENAI_HTTP_CACHE_DIR


def _build_openai_session(cache_dir: Path, cache_enabled: bool) -> requests.Session:
    if not cache_enabled:
        return requests.Session()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = cache_dir / DEFAULT_OPENAI_HTTP_CACHE_NAME
    return cast(
        requests.Session,
        CachedSession(
            cache_name=str(cache_name),
            backend="sqlite",
            expire_after=-1,
            allowable_methods=("GET", "POST"),
            allowable_codes=(200,),
        ),
    )


def _resolve_elevenlabs_http_cache_enabled(config: bool | None) -> bool:
    if config is not None:
        return config
    value = os.getenv("ELEVENLABS_HTTP_CACHE", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _resolve_elevenlabs_http_cache_dir(config: Path | None) -> Path:
    if config is not None:
        return config
    value = os.getenv("ELEVENLABS_HTTP_CACHE_DIR", "").strip()
    if value:
        return Path(value)
    return DEFAULT_ELEVENLABS_HTTP_CACHE_DIR


def _build_elevenlabs_session(cache_dir: Path, cache_enabled: bool) -> requests.Session:
    if not cache_enabled:
        return requests.Session()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = cache_dir / DEFAULT_ELEVENLABS_HTTP_CACHE_NAME
    return cast(
        requests.Session,
        CachedSession(
            cache_name=str(cache_name),
            backend="sqlite",
            expire_after=-1,
            allowable_methods=("GET", "POST"),
            allowable_codes=(200,),
        ),
    )


@dataclass(frozen=True)
class AudioRenderResult:
    chapter_count: int
    manifest_in_path: Path
    manifest_out_path: Path
    chapters_audio_dir: Path
    merged_audio_path: Path | None
    total_duration_seconds: float
    chapter_markers_embedded: bool
    chapters_rendered: int
    chapters_reused: int


def render_audio_from_manifest(
    manifest_path: Path,
    out_dir: Path,
    client: TtsClient,
    output_format: str = "mp3",
    merge_output: bool = True,
    out_manifest_path: Path | None = None,
    probe_duration: DurationProbe | None = None,
    merge_audio: AudioMerger | None = None,
    embed_chapters: bool = True,
    embed_chapter_markers: ChapterMarkerEmbedder | None = None,
    render_fingerprint: str = "",
    provider: str = "openai",
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
    embed_fn = embed_chapter_markers or embed_mp3_chapters

    start_seconds = 0.0
    rendered_paths: list[Path] = []
    chapters_rendered = 0
    chapters_reused = 0
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
        text_sha256 = _text_sha256(text)
        can_reuse = _can_reuse_chapter_audio(
            chapter=chapter,
            audio_path=audio_path,
            text_sha256=text_sha256,
            render_fingerprint=render_fingerprint,
        )
        if can_reuse:
            chapters_reused += 1
        else:
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
            chapters_rendered += 1

        duration_seconds = _duration_for_chapter(chapter, audio_path, probe_fn)
        chapter["audio_path"] = str(audio_path.as_posix())
        chapter["duration_seconds"] = round(duration_seconds, 3)
        chapter["start_seconds"] = round(start_seconds, 3)
        chapter["text_sha256"] = text_sha256
        chapter["render_fingerprint"] = render_fingerprint
        start_seconds += duration_seconds
        rendered_paths.append(audio_path)

    merged_audio_path: Path | None = None
    chapter_markers_embedded = False
    if merge_output and rendered_paths:
        merged_audio_path = out_dir / f"extra_facts_audio.{output_format}"
        merge_fn(rendered_paths, merged_audio_path)
        if embed_chapters and output_format == "mp3":
            embed_fn(chapters, merged_audio_path)
            chapter_markers_embedded = True

    payload["audio_render"] = {
        "provider": provider,
        "output_format": output_format,
        "merged_audio_path": (
            str(merged_audio_path.as_posix()) if merged_audio_path is not None else None
        ),
        "total_duration_seconds": round(start_seconds, 3),
        "chapter_markers_embedded": chapter_markers_embedded,
        "chapters_rendered": chapters_rendered,
        "chapters_reused": chapters_reused,
        "render_fingerprint": render_fingerprint,
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
        chapter_markers_embedded=chapter_markers_embedded,
        chapters_rendered=chapters_rendered,
        chapters_reused=chapters_reused,
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


def embed_mp3_chapters(chapters: list[dict[str, Any]], merged_audio_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ffmetadata") as metadata_file:
        metadata_path = Path(metadata_file.name)
        metadata_file.write(";FFMETADATA1\n")
        for chapter in chapters:
            start_seconds = float(chapter.get("start_seconds", 0.0))
            duration_seconds = float(chapter.get("duration_seconds", 0.0))
            start_ms = max(0, round(start_seconds * 1000))
            end_ms = max(start_ms + 1, round((start_seconds + duration_seconds) * 1000))
            raw_title = chapter.get("title") or chapter.get("code") or "Chapter"
            title = _escape_ffmetadata_value(str(raw_title))
            metadata_file.write("[CHAPTER]\n")
            metadata_file.write("TIMEBASE=1/1000\n")
            metadata_file.write(f"START={start_ms}\n")
            metadata_file.write(f"END={end_ms}\n")
            metadata_file.write(f"title={title}\n")

    output_with_chapters = merged_audio_path.with_suffix(".chapters.mp3")
    try:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(merged_audio_path),
            "-i",
            str(metadata_path),
            "-map_metadata",
            "1",
            "-codec",
            "copy",
            str(output_with_chapters),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        output_with_chapters.replace(merged_audio_path)
    finally:
        metadata_path.unlink(missing_ok=True)
        output_with_chapters.unlink(missing_ok=True)


def _resolve_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return (manifest_path.parent / path).resolve()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _can_reuse_chapter_audio(
    chapter: dict[str, Any],
    audio_path: Path,
    text_sha256: str,
    render_fingerprint: str,
) -> bool:
    existing_hash = chapter.get("text_sha256")
    existing_fingerprint = chapter.get("render_fingerprint")
    if not isinstance(existing_hash, str):
        return False
    if existing_hash != text_sha256:
        return False
    if existing_fingerprint != render_fingerprint:
        return False
    return audio_path.exists()


def _duration_for_chapter(
    chapter: dict[str, Any],
    audio_path: Path,
    probe_fn: DurationProbe,
) -> float:
    existing = chapter.get("duration_seconds")
    if isinstance(existing, int | float) and existing > 0:
        return float(existing)
    return probe_fn(audio_path)


def _escape_ffmetadata_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("=", "\\=")
    escaped = escaped.replace(";", "\\;")
    escaped = escaped.replace("#", "\\#")
    return escaped


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
