from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import requests
from _pytest.monkeypatch import MonkeyPatch

import extra_facts.audio as audio_module
from extra_facts.audio import (
    DEFAULT_ELEVENLABS_OUTPUT_FORMAT,
    DEFAULT_TTS_INSTRUCTIONS,
    ElevenLabsTtsClient,
    OpenAITtsClient,
    render_audio_from_manifest,
)


class _FakeTtsClient:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str) -> bytes:
        self.calls += 1
        return f"audio:{text[:16]}".encode()


class _FailAfterOneTtsClient:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str) -> bytes:
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("simulated credits exhausted")
        return f"audio:{text[:16]}".encode()


class _CapturingTtsClient:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.inputs.append(text)
        return b"audio-bytes"




def test_render_audio_from_manifest_rewrites_pause_markers_for_openai(tmp_path: Path) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("Question one.\n[[SHORT_PAUSE]]\nQuestion two.", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 1,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_path),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    client = _CapturingTtsClient()

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=client,
        merge_output=False,
        probe_duration=lambda _path: 5.0,
        render_fingerprint="test-fingerprint",
        provider="openai",
    )

    assert result.chapter_count == 1
    assert client.inputs == ["Question one.\n...\nQuestion two."]


def test_render_audio_from_manifest_rewrites_pause_markers_for_elevenlabs(tmp_path: Path) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("Question one.\n[[SHORT_PAUSE]]\nQuestion two.", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 1,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_path),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    client = _CapturingTtsClient()

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=client,
        merge_output=False,
        probe_duration=lambda _path: 5.0,
        render_fingerprint="test-fingerprint",
        provider="elevenlabs",
    )

    assert result.chapter_count == 1
    assert client.inputs == ["Question one.\n... ...\nQuestion two."]

def test_render_audio_from_manifest_enriches_manifest_and_merges(tmp_path: Path) -> None:
    chapters_dir = tmp_path / "audio" / "chapters"
    chapters_dir.mkdir(parents=True)
    chapter_1 = chapters_dir / "chapter-01.txt"
    chapter_2 = chapters_dir / "chapter-02.txt"
    chapter_1.write_text("Chapter one text", encoding="utf-8")
    chapter_2.write_text("Chapter two text", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 2,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_1),
            },
            {
                "number": 2,
                "code": "E2",
                "title": "Two",
                "groups": ["E2A"],
                "text_path": str(chapter_2),
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    merge_calls: list[list[Path]] = []
    embed_calls: list[tuple[list[dict[str, object]], Path]] = []

    def _probe(path: Path) -> float:
        if path.name == "chapter-01.mp3":
            return 10.0
        return 12.5

    def _merge(inputs: list[Path], output: Path) -> None:
        merge_calls.append(inputs)
        output.write_bytes(b"merged-audio")

    def _embed(chapters: list[dict[str, object]], merged_audio_path: Path) -> None:
        embed_calls.append((chapters, merged_audio_path))

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=_FakeTtsClient(),
        output_format="mp3",
        merge_output=True,
        probe_duration=_probe,
        merge_audio=_merge,
        embed_chapter_markers=_embed,
        render_fingerprint="test-fingerprint",
    )

    assert result.chapter_count == 2
    assert (tmp_path / "audio" / "chapters" / "chapter-01.mp3").exists()
    assert (tmp_path / "audio" / "chapters" / "chapter-02.mp3").exists()
    assert result.merged_audio_path == (tmp_path / "audio" / "book.mp3")
    assert result.merged_audio_path is not None
    assert result.merged_audio_path.exists()
    assert len(merge_calls) == 1
    assert [path.name for path in merge_calls[0]] == ["chapter-01.mp3", "chapter-02.mp3"]
    assert len(embed_calls) == 1
    assert embed_calls[0][1] == result.merged_audio_path
    assert result.chapter_markers_embedded is True
    assert result.chapters_rendered == 2
    assert result.chapters_reused == 0

    enriched = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapters = enriched["chapters"]
    assert chapters[0]["audio_path"].endswith("chapter-01.mp3")
    assert chapters[0]["duration_seconds"] == 10.0
    assert chapters[0]["start_seconds"] == 0.0
    assert chapters[1]["duration_seconds"] == 12.5
    assert chapters[1]["start_seconds"] == 10.0
    assert chapters[0]["render_fingerprint"] == "test-fingerprint"
    assert isinstance(chapters[0]["text_sha256"], str)
    assert enriched["audio_render"]["total_duration_seconds"] == 22.5
    assert enriched["audio_render"]["chapter_markers_embedded"] is True
    assert enriched["audio_render"]["chapters_rendered"] == 2
    assert enriched["audio_render"]["chapters_reused"] == 0


def test_render_audio_from_manifest_supports_no_merge(tmp_path: Path) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("Only chapter", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 1,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_path),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def _probe_fixed(_path: Path) -> float:
        return 5.0

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=_FakeTtsClient(),
        merge_output=False,
        probe_duration=_probe_fixed,
        render_fingerprint="test-fingerprint",
    )
    assert result.merged_audio_path is None
    assert result.chapter_markers_embedded is False


def test_render_audio_from_manifest_supports_no_chapter_markers(tmp_path: Path) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("Only chapter", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 1,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_path),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def _probe_fixed(_path: Path) -> float:
        return 5.0

    def _merge(inputs: list[Path], output: Path) -> None:
        _ = inputs
        output.write_bytes(b"merged-audio")

    result = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=_FakeTtsClient(),
        merge_output=True,
        probe_duration=_probe_fixed,
        merge_audio=_merge,
        embed_chapters=False,
        render_fingerprint="test-fingerprint",
    )
    assert result.chapter_markers_embedded is False


def test_render_audio_from_manifest_reuses_unchanged_chapters(tmp_path: Path) -> None:
    chapters_dir = tmp_path / "audio" / "chapters"
    chapters_dir.mkdir(parents=True)
    chapter_1 = chapters_dir / "chapter-01.txt"
    chapter_2 = chapters_dir / "chapter-02.txt"
    chapter_1.write_text("Chapter one text", encoding="utf-8")
    chapter_2.write_text("Chapter two text", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 2,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_1),
            },
            {
                "number": 2,
                "code": "E2",
                "title": "Two",
                "groups": ["E2A"],
                "text_path": str(chapter_2),
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    first_client = _FakeTtsClient()
    first = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=first_client,
        merge_output=False,
        probe_duration=lambda _path: 5.0,
        render_fingerprint="fp-v1",
    )
    assert first_client.calls == 2
    assert first.chapters_rendered == 2
    assert first.chapters_reused == 0

    second_client = _FakeTtsClient()
    second = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=second_client,
        merge_output=False,
        probe_duration=lambda _path: 5.0,
        render_fingerprint="fp-v1",
    )
    assert second_client.calls == 0
    assert second.chapters_rendered == 0
    assert second.chapters_reused == 2


def test_render_audio_from_manifest_checkpoints_progress_for_resume(tmp_path: Path) -> None:
    chapters_dir = tmp_path / "audio" / "chapters"
    chapters_dir.mkdir(parents=True)
    chapter_1 = chapters_dir / "chapter-01.txt"
    chapter_2 = chapters_dir / "chapter-02.txt"
    chapter_1.write_text("Chapter one text", encoding="utf-8")
    chapter_2.write_text("Chapter two text", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest = {
        "schema_version": 1,
        "chapter_count": 2,
        "chapters": [
            {
                "number": 1,
                "code": "E1",
                "title": "One",
                "groups": ["E1A"],
                "text_path": str(chapter_1),
            },
            {
                "number": 2,
                "code": "E2",
                "title": "Two",
                "groups": ["E2A"],
                "text_path": str(chapter_2),
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="credits exhausted"):
        _ = render_audio_from_manifest(
            manifest_path=manifest_path,
            out_dir=tmp_path / "audio",
            client=_FailAfterOneTtsClient(),
            merge_output=False,
            probe_duration=lambda _path: 5.0,
            render_fingerprint="resume-fingerprint",
        )

    checkpointed = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapter_entries = checkpointed["chapters"]
    assert chapter_entries[0]["audio_path"].endswith("chapter-01.mp3")
    assert chapter_entries[0]["render_fingerprint"] == "resume-fingerprint"
    assert isinstance(chapter_entries[0]["text_sha256"], str)
    assert "audio_path" not in chapter_entries[1]

    resume_client = _FakeTtsClient()
    resumed = render_audio_from_manifest(
        manifest_path=manifest_path,
        out_dir=tmp_path / "audio",
        client=resume_client,
        merge_output=False,
        probe_duration=lambda _path: 5.0,
        render_fingerprint="resume-fingerprint",
    )
    assert resume_client.calls == 1
    assert resumed.chapters_reused == 1
    assert resumed.chapters_rendered == 1


def test_render_audio_from_manifest_chunks_at_paragraph_boundaries(tmp_path: Path) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text(
        "Paragraph one.\n\nParagraph two is here.\n\nParagraph three.",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "chapter_count": 1,
                "chapters": [
                    {
                        "number": 1,
                        "code": "E1",
                        "title": "One",
                        "groups": ["E1A"],
                        "text_path": str(chapter_path),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    client = _CapturingTtsClient()
    def _merge(_inputs: list[Path], output: Path) -> None:
        output.write_bytes(b"merged-audio")
    original_max = audio_module.TTS_MAX_CHARS
    audio_module.TTS_MAX_CHARS = 30
    try:
        _ = render_audio_from_manifest(
            manifest_path=manifest_path,
            out_dir=tmp_path / "audio",
            client=client,
            merge_output=False,
            merge_audio=_merge,
            probe_duration=lambda _path: 1.0,
            render_fingerprint="test-fingerprint",
        )
    finally:
        audio_module.TTS_MAX_CHARS = original_max

    assert client.inputs == [
        "Paragraph one.",
        "Paragraph two is here.",
        "Paragraph three.",
    ]


def test_render_audio_from_manifest_splits_oversize_paragraph_without_breaking_words(
    tmp_path: Path,
) -> None:
    chapter_path = tmp_path / "audio" / "chapters" / "chapter-01.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text(
        "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "audio" / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "chapter_count": 1,
                "chapters": [
                    {
                        "number": 1,
                        "code": "E1",
                        "title": "One",
                        "groups": ["E1A"],
                        "text_path": str(chapter_path),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    client = _CapturingTtsClient()
    def _merge(_inputs: list[Path], output: Path) -> None:
        output.write_bytes(b"merged-audio")
    original_max = audio_module.TTS_MAX_CHARS
    audio_module.TTS_MAX_CHARS = 18
    try:
        _ = render_audio_from_manifest(
            manifest_path=manifest_path,
            out_dir=tmp_path / "audio",
            client=client,
            merge_output=False,
            merge_audio=_merge,
            probe_duration=lambda _path: 1.0,
            render_fingerprint="test-fingerprint",
        )
    finally:
        audio_module.TTS_MAX_CHARS = original_max

    assert client.inputs == [
        "alpha beta gamma",
        "delta epsilon zeta",
        "eta theta iota",
        "kappa",
    ]


def test_openai_tts_http_cache_enabled_defaults_true(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_HTTP_CACHE", raising=False)
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    assert client.cache_enabled is True


def test_openai_tts_http_cache_enabled_env_false(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_HTTP_CACHE", "false")
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    assert client.cache_enabled is False


def test_openai_tts_http_cache_dir_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_HTTP_CACHE_DIR", "/tmp/openai-http-cache-audio")
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    assert client.cache_dir == Path("/tmp/openai-http-cache-audio")


class _RecordingResponse:
    def __init__(
        self,
        status_code: int,
        content: bytes,
        text: str = "",
        headers: dict[str, str] | None = None,
        from_cache: bool = False,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = headers or {}
        self.from_cache = from_cache


class _RecordingSession:
    def __init__(self, response: _RecordingResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
        params: dict[str, object] | None = None,
    ) -> _RecordingResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
                "params": params,
            }
        )
        return self.response


class _SequenceSession:
    def __init__(self, responses: list[_RecordingResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
        params: dict[str, object] | None = None,
    ) -> _RecordingResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
                "params": params,
            }
        )
        return self.responses.pop(0)

    def __enter__(self) -> _SequenceSession:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_openai_tts_synthesize_uses_audio_speech_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    session = _RecordingSession(
        _RecordingResponse(
            status_code=200,
            content=b"audio-bytes",
            headers={"Content-Type": "audio/mpeg"},
        )
    )
    client._session = cast(requests.Session, session)  # pyright: ignore[reportPrivateUsage]

    rendered = client.synthesize("hello")

    assert rendered == b"audio-bytes"
    assert len(session.calls) == 1
    assert session.calls[0]["url"] == "https://api.openai.com/v1/audio/speech"
    request_payload = cast(dict[str, object], session.calls[0]["json"])
    assert request_payload["model"] == "gpt-4o-mini-tts"
    assert request_payload["voice"] == "alloy"
    assert request_payload["speed"] == 1.0
    assert request_payload["instructions"] == DEFAULT_TTS_INSTRUCTIONS


def test_openai_tts_synthesize_raises_without_responses_fallback(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    cached_or_primary_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=400,
                content=b"",
                text='{"error":"bad request"}',
                headers={"Content-Type": "application/json"},
            )
        ]
    )
    uncached_retry_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=401,
                content=b"",
                text='{"error":"retry unauthorized"}',
                headers={"Content-Type": "application/json"},
            )
        ]
    )
    client._session = cast(requests.Session, cached_or_primary_session)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(
        requests,
        "Session",
        lambda: cast(requests.Session, uncached_retry_session),
    )

    with pytest.raises(RuntimeError, match=r"first attempt \(400, from_cache=False\)"):
        client.synthesize("hello")

    assert len(cached_or_primary_session.calls) == 1
    assert len(uncached_retry_session.calls) == 1


def test_openai_tts_synthesize_includes_instructions(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAITtsClient(
        model="gpt-4o-mini-tts",
        voice="alloy",
        instructions="Warm, engaging delivery with varied intonation.",
    )
    session = _RecordingSession(
        _RecordingResponse(
            status_code=200,
            content=b"audio-bytes",
            headers={"Content-Type": "audio/mpeg"},
        )
    )
    client._session = cast(requests.Session, session)  # pyright: ignore[reportPrivateUsage]

    _ = client.synthesize("hello")

    request_payload = cast(dict[str, object], session.calls[0]["json"])
    assert request_payload["instructions"] == "Warm, engaging delivery with varied intonation."


def test_openai_tts_retries_uncached_when_cached_error_returned(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAITtsClient(model="gpt-4o-mini-tts", voice="alloy")
    cached_error_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=404,
                content=b"",
                text='{"error":"stale cached error"}',
                headers={"Content-Type": "application/json"},
                from_cache=True,
            )
        ]
    )
    uncached_success_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=200,
                content=b"audio-bytes",
                headers={"Content-Type": "audio/mpeg"},
            )
        ]
    )
    client._session = cast(requests.Session, cached_error_session)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(
        requests,
        "Session",
        lambda: cast(requests.Session, uncached_success_session),
    )

    rendered = client.synthesize("hello")

    assert rendered == b"audio-bytes"
    assert len(cached_error_session.calls) == 1
    assert len(uncached_success_session.calls) == 1


def test_elevenlabs_tts_http_cache_enabled_defaults_true(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("ELEVENLABS_HTTP_CACHE", raising=False)
    client = ElevenLabsTtsClient(model="eleven_multilingual_v2", voice_id="voice-id")
    assert client.cache_enabled is True


def test_elevenlabs_tts_http_cache_enabled_env_false(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_HTTP_CACHE", "false")
    client = ElevenLabsTtsClient(model="eleven_multilingual_v2", voice_id="voice-id")
    assert client.cache_enabled is False


def test_elevenlabs_tts_http_cache_dir_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_HTTP_CACHE_DIR", "/tmp/elevenlabs-http-cache-audio")
    client = ElevenLabsTtsClient(model="eleven_multilingual_v2", voice_id="voice-id")
    assert client.cache_dir == Path("/tmp/elevenlabs-http-cache-audio")


def test_elevenlabs_tts_synthesize_uses_tts_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    client = ElevenLabsTtsClient(model="eleven_multilingual_v2", voice_id="voice-id")
    session = _RecordingSession(
        _RecordingResponse(
            status_code=200,
            content=b"audio-bytes",
            headers={"Content-Type": "audio/mpeg"},
        )
    )
    client._session = cast(requests.Session, session)  # pyright: ignore[reportPrivateUsage]

    rendered = client.synthesize("hello")

    assert rendered == b"audio-bytes"
    assert len(session.calls) == 1
    assert session.calls[0]["url"] == "https://api.elevenlabs.io/v1/text-to-speech/voice-id"
    request_payload = cast(dict[str, object], session.calls[0]["json"])
    assert request_payload["model_id"] == "eleven_multilingual_v2"
    assert request_payload["text"] == "hello"
    assert request_payload["language_code"] == "en"
    request_params = cast(dict[str, object], session.calls[0]["params"])
    assert request_params["output_format"] == DEFAULT_ELEVENLABS_OUTPUT_FORMAT


def test_elevenlabs_tts_synthesize_supports_custom_language_code(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    client = ElevenLabsTtsClient(
        model="eleven_multilingual_v2",
        voice_id="voice-id",
        language_code="es",
    )
    session = _RecordingSession(
        _RecordingResponse(
            status_code=200,
            content=b"audio-bytes",
            headers={"Content-Type": "audio/mpeg"},
        )
    )
    client._session = cast(requests.Session, session)  # pyright: ignore[reportPrivateUsage]

    _ = client.synthesize("hola")

    request_payload = cast(dict[str, object], session.calls[0]["json"])
    assert request_payload["language_code"] == "es"


def test_elevenlabs_tts_retries_uncached_when_cached_error_returned(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    client = ElevenLabsTtsClient(model="eleven_multilingual_v2", voice_id="voice-id")
    cached_error_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=404,
                content=b"",
                text='{"error":"stale cached error"}',
                headers={"Content-Type": "application/json"},
                from_cache=True,
            )
        ]
    )
    uncached_success_session = _SequenceSession(
        [
            _RecordingResponse(
                status_code=200,
                content=b"audio-bytes",
                headers={"Content-Type": "audio/mpeg"},
            )
        ]
    )
    client._session = cast(requests.Session, cached_error_session)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(
        requests,
        "Session",
        lambda: cast(requests.Session, uncached_success_session),
    )

    rendered = client.synthesize("hello")

    assert rendered == b"audio-bytes"
    assert len(cached_error_session.calls) == 1
    assert len(uncached_success_session.calls) == 1
