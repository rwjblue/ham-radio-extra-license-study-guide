from __future__ import annotations

from pytest import MonkeyPatch

from extra_facts.cli import create_parser, resolve_tts_provider


def test_resolve_tts_provider_prefers_explicit_value() -> None:
    assert resolve_tts_provider("openai") == "openai"
    assert resolve_tts_provider("elevenlabs") == "elevenlabs"


def test_resolve_tts_provider_prefers_elevenlabs_when_key_present(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")

    assert resolve_tts_provider(None) == "elevenlabs"


def test_resolve_tts_provider_falls_back_to_openai_when_elevenlabs_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")

    assert resolve_tts_provider(None) == "openai"


def test_resolve_tts_provider_defaults_to_elevenlabs_when_no_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert resolve_tts_provider(None) == "elevenlabs"


def test_audio_render_qc_defaults_enabled() -> None:
    parser = create_parser()
    args = parser.parse_args(["audio-render"])
    assert args.qc_openai_transcribe is True


def test_audio_render_qc_can_be_disabled() -> None:
    parser = create_parser()
    args = parser.parse_args(["audio-render", "--no-qc-openai-transcribe"])
    assert args.qc_openai_transcribe is False


def test_audio_render_llm_judge_flag() -> None:
    parser = create_parser()
    args = parser.parse_args(["audio-render", "--qc-llm-judge", "--qc-llm-model", "gpt-4.1-mini"])
    assert args.qc_llm_judge is True
    assert args.qc_llm_model == "gpt-4.1-mini"
