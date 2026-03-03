from __future__ import annotations

from extra_facts.tts_pause import (
    AUDIO_SHORT_PAUSE_MARKER,
    apply_provider_pause_markers,
    provider_short_pause_text,
)


def test_provider_short_pause_text_defaults_to_openai_style() -> None:
    assert provider_short_pause_text("openai") == "..."
    assert provider_short_pause_text("unknown") == "..."


def test_provider_short_pause_text_uses_longer_pause_for_elevenlabs() -> None:
    assert provider_short_pause_text("elevenlabs") == "... ..."


def test_apply_provider_pause_markers_rewrites_marker() -> None:
    text = f"First question.\n{AUDIO_SHORT_PAUSE_MARKER}\nSecond question."
    assert (
        apply_provider_pause_markers(text, provider="openai")
        == "First question.\n...\nSecond question."
    )
    assert (
        apply_provider_pause_markers(text, provider="elevenlabs")
        == "First question.\n... ...\nSecond question."
    )
