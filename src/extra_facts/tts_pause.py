from __future__ import annotations

AUDIO_SHORT_PAUSE_MARKER = "[[SHORT_PAUSE]]"


def provider_short_pause_text(provider: str) -> str:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "elevenlabs":
        # ElevenLabs tends to realize a slightly longer separation with two ellipsis groups.
        return "... ..."
    # Default and OpenAI behavior.
    return "..."


def apply_provider_pause_markers(text: str, provider: str) -> str:
    if AUDIO_SHORT_PAUSE_MARKER not in text:
        return text
    return text.replace(AUDIO_SHORT_PAUSE_MARKER, provider_short_pause_text(provider))
