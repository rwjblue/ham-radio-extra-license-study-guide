from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from extra_facts.audio import OpenAITtsClient, render_audio_from_manifest


class _FakeTtsClient:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str) -> bytes:
        self.calls += 1
        return f"audio:{text[:16]}".encode()


def test_render_audio_from_manifest_enriches_manifest_and_merges(tmp_path: Path) -> None:
    chapters_dir = tmp_path / "audio" / "chapters"
    chapters_dir.mkdir(parents=True)
    chapter_1 = chapters_dir / "chapter-01.txt"
    chapter_2 = chapters_dir / "chapter-02.txt"
    chapter_1.write_text("Chapter one text", encoding="utf-8")
    chapter_2.write_text("Chapter two text", encoding="utf-8")

    manifest_path = tmp_path / "audio" / "audio_chapters_manifest.json"
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
    assert result.merged_audio_path == (tmp_path / "audio" / "extra_facts_audio.mp3")
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

    manifest_path = tmp_path / "audio" / "audio_chapters_manifest.json"
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

    manifest_path = tmp_path / "audio" / "audio_chapters_manifest.json"
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

    manifest_path = tmp_path / "audio" / "audio_chapters_manifest.json"
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
